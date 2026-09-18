<#
.SYNOPSIS
    WordMem (Qt/C++) Windows 一键构建：CMake+Ninja 编译 -> windeployqt 收集依赖
    -> Inno Setup 生成安装包。本地与 CI 通用。

.DESCRIPTION
    对应旧 Python 版 scripts/build_windows.py 的 C++ 迁移版本。
    自动定位 Visual Studio（vswhere）、CMake/Ninja（优先 VS 自带）与 Qt 前缀。

.PARAMETER QtDir
    Qt msvc2022_64 前缀目录（如 D:\Qt\6.8.3\msvc2022_64）。留空则按
    CMAKE_PREFIX_PATH / Qt6_Dir / 常见安装路径自动探测。

.PARAMETER BuildType
    CMake 构建类型，默认 Release。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File cpp\scripts\build_windows.ps1 -QtDir D:\Qt\6.8.3\msvc2022_64

.EXAMPLE
    # CI：跳过安装包，仅编译 + 测试 + 部署
    powershell -File cpp\scripts\build_windows.ps1 -SkipInstaller
#>
[CmdletBinding()]
param(
    [string]$QtDir = '',
    [string]$BuildType = 'Release',
    [string]$Arch = 'x64',
    [switch]$SkipTests,
    [switch]$SkipDeploy,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'

# 统一 UTF-8 输出，避免 CI（cp1252）打印中文报错
foreach ($s in @([Console]::Out, [Console]::Error)) {
    try { $s.OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$CppDir    = Resolve-Path (Join-Path $ScriptDir '..')
$Root      = Resolve-Path (Join-Path $CppDir '..')
$BuildDir  = Join-Path $CppDir 'build'
$StageDir  = Join-Path $Root 'dist\WordMem'

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 定位 Qt 前缀
function Test-QtPrefix($p) {
    return ($p -and (Test-Path (Join-Path $p 'bin\qmake.exe')) -and (Test-Path (Join-Path $p 'lib\cmake\Qt6')))
}

function Resolve-QtPrefix {
    # 按优先级收集候选，逐个校验（须含 bin\qmake.exe 与 lib\cmake\Qt6），取第一个有效者
    $candidates = @()
    if ($QtDir) { $candidates += $QtDir }
    # qmake 在 PATH 时（CI 的 install-qt-action 会加入），直接查询前缀，最权威
    $qmake = Get-Command qmake -ErrorAction SilentlyContinue
    if ($qmake) { $candidates += (& qmake -query QT_INSTALL_PREFIX 2>$null | Select-Object -First 1) }
    if ($env:CMAKE_PREFIX_PATH) { $candidates += ($env:CMAKE_PREFIX_PATH -split ';') }
    if ($env:Qt6_Dir) { $candidates += (Join-Path $env:Qt6_Dir '..\..\..') }
    foreach ($rootDir in @($env:QT_ROOT, 'D:\Qt', 'C:\Qt')) {
        if ($rootDir -and (Test-Path $rootDir)) {
            $candidates += (Get-ChildItem -Path $rootDir -Directory -Filter '6.*' -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName 'msvc2022_64' })
        }
    }
    foreach ($c in $candidates) {
        if (-not $c) { continue }
        $full = $null
        try { $full = (Resolve-Path $c.Trim() -ErrorAction Stop).Path } catch { continue }
        if (Test-QtPrefix $full) { return $full }
    }
    throw '未能定位有效的 Qt 前缀（需含 bin\qmake.exe 与 lib\cmake\Qt6），请用 -QtDir 指定'
}

# ---------------------------------------------------------------- 定位 Visual Studio
function Enter-VsEnv {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) { $vswhere = Join-Path $env:ProgramFiles 'Microsoft Visual Studio\Installer\vswhere.exe' }
    if (-not (Test-Path $vswhere)) { throw '未找到 vswhere.exe，请安装 Visual Studio 2022（含 C++ 工作负载）' }
    $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1
    if (-not $vsPath) { throw 'vswhere 未找到带 C++ 工具集的 Visual Studio 实例' }
    Write-Host "VS: $vsPath"
    Import-Module (Join-Path $vsPath 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
    Enter-VsDevShell -VsInstallPath $vsPath -SkipAutomaticLocation -DevCmdArguments "-arch=$Arch -host_arch=x64" | Out-Null
    return $vsPath
}

# ---------------------------------------------------------------- 定位 CMake / Ninja / ctest
function Resolve-CMake($vsPath) {
    $vsCMakeBin = Join-Path $vsPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin'
    $vsCMake = Join-Path $vsCMakeBin 'cmake.exe'
    $pathCMake = Get-Command cmake -ErrorAction SilentlyContinue
    # 优先使用 VS 自带（版本足够新）；PATH 中的可能过旧
    if (Test-Path $vsCMake) {
        $script:CMAKE = $vsCMake
        $script:CTEST = Join-Path $vsCMakeBin 'ctest.exe'
        $env:PATH = "$vsCMakeBin;$env:PATH"   # 让 ninja 可见
    } elseif ($pathCMake) {
        $script:CMAKE = $pathCMake.Source
        $script:CTEST = 'ctest'
    } else {
        throw '未找到 cmake.exe'
    }
    Write-Host "cmake: $script:CMAKE"
}

# ---------------------------------------------------------------- Inno Setup 中文语言包（缺失则下载，失败回退英文）
function Ensure-ChineseIsl {
    $isl = Join-Path $Root 'packaging\Languages\ChineseSimplified.isl'
    if ((Test-Path $isl) -and ((Get-Item $isl).Length -gt 10000)) { return }
    New-Item -ItemType Directory -Force -Path (Split-Path $isl) | Out-Null
    $urls = @(
        'https://cdn.jsdelivr.net/gh/jrsoftware/issrc@main/Files/Languages/ChineseSimplified.isl',
        'https://raw.githubusercontent.com/jrsoftware/issrc/main/Files/Languages/ChineseSimplified.isl'
    )
    foreach ($u in $urls) {
        try {
            Write-Host "下载中文语言包: $u"
            Invoke-WebRequest -Uri $u -OutFile $isl -TimeoutSec 30
            if ((Get-Item $isl).Length -gt 10000) { return }
        } catch { Write-Host "  失败: $($_.Exception.Message)" }
    }
    Write-Warning '中文语言包下载失败，安装向导将回退英文界面。'
}

function Find-Iscc {
    $local = $env:LOCALAPPDATA
    $cands = @(
        (Join-Path $Root 'packaging\ISCC.exe'),
        $(if ($local) { Join-Path $local 'Programs\Inno Setup 6\ISCC.exe' } else { $null }),
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    )
    foreach ($c in $cands) { if ($c -and (Test-Path $c)) { return $c } }
    $w = Get-Command ISCC -ErrorAction SilentlyContinue
    if ($w) { return $w.Source }
    throw '未找到 Inno Setup（ISCC.exe）。请安装：winget install --id JRSoftware.InnoSetup -e'
}

function Read-Version {
    $txt = Get-Content (Join-Path $CppDir 'CMakeLists.txt') -Raw
    $m = [regex]::Match($txt, 'project\(WordMem\s+VERSION\s+([0-9.]+)')
    if (-not $m.Success) { throw '无法从 CMakeLists.txt 解析版本号' }
    return $m.Groups[1].Value
}

# ---------------------------------------------------------------- 拷贝 VC++ 运行库 DLL
function Copy-VcRuntime($vsPath, $dest) {
    # 从 VS 的 MSVC Redist 目录拷贝 CRT，使产物免依赖系统已装的 VC++ 运行库
    $crtDir = Get-ChildItem -Path (Join-Path $vsPath 'VC\Redist\MSVC') -Directory -ErrorAction SilentlyContinue |
              Sort-Object Name -Descending |
              ForEach-Object { Get-ChildItem -Path (Join-Path $_.FullName 'x64') -Directory -Filter 'Microsoft.VC*.CRT' -ErrorAction SilentlyContinue } |
              Select-Object -First 1
    if (-not $crtDir) { Write-Warning '未找到 VC Redist CRT 目录，跳过（目标机需已装 VC++ 运行库）'; return }
    foreach ($dll in @('msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll')) {
        $src = Join-Path $crtDir.FullName $dll
        if (Test-Path $src) { Copy-Item $src $dest -Force }
    }
    Write-Host "已拷贝 VC 运行库: $($crtDir.Name)"
}

# ================================================================ 主流程
$QtPrefix = Resolve-QtPrefix
Write-Host "Qt 前缀: $QtPrefix"
$vsPath = Enter-VsEnv
Resolve-CMake $vsPath
$env:PATH = "$QtPrefix\bin;$env:PATH"   # 运行测试 / windeployqt 需要 Qt DLL

Step "配置 (CMake + Ninja, $BuildType)"
& $CMAKE -S $CppDir -B $BuildDir -G Ninja `
    "-DCMAKE_BUILD_TYPE=$BuildType" `
    "-DCMAKE_PREFIX_PATH=$QtPrefix"
if ($LASTEXITCODE -ne 0) { throw 'CMake 配置失败' }

Step '编译'
& $CMAKE --build $BuildDir
if ($LASTEXITCODE -ne 0) { throw '编译失败' }

$exe = Join-Path $BuildDir 'WordMem.exe'
if (-not (Test-Path $exe)) { throw "未找到产物: $exe" }

if (-not $SkipTests) {
    Step '单元测试 (ctest)'
    & $CMAKE --build $BuildDir  # 确保测试目标已构建
    & $script:CTEST --test-dir $BuildDir --output-on-failure
    if ($LASTEXITCODE -ne 0) { throw '测试未通过' }
}

if (-not $SkipDeploy) {
    Step '部署运行时依赖 (windeployqt)'
    if (Test-Path $StageDir) { Remove-Item -Recurse -Force $StageDir }
    New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
    Copy-Item $exe $StageDir
    $wdq = Join-Path $QtPrefix 'bin\windeployqt.exe'
    # 不用 --compiler-runtime（它会放 25MB 的 vc_redist 引导器，需管理员）；
    # 改为直接拷贝 CRT 运行库 DLL，得到自包含、免安装、用户级的包。
    & $wdq --release --no-compiler-runtime --no-translations `
        --no-system-d3d-compiler --no-opengl-sw `
        (Join-Path $StageDir 'WordMem.exe')
    if ($LASTEXITCODE -ne 0) { throw 'windeployqt 失败' }
    Copy-VcRuntime $vsPath $StageDir
}

if (-not $SkipInstaller) {
    Step '生成安装包 (Inno Setup)'
    Ensure-ChineseIsl
    $iscc = Find-Iscc
    $version = Read-Version
    & $iscc "/DAPP_VERSION=$version" (Join-Path $Root 'packaging\installer.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup 打包失败' }
    Write-Host "安装包: dist\WordMem-$version-setup.exe" -ForegroundColor Green
}

Step '完成'
Write-Host "产物目录: $StageDir"
