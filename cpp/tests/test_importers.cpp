// 词库解析测试：清洗、词性切分、各格式 parser 与自动路由。
#include <QFile>
#include <QJsonArray>
#include <QJsonObject>
#include <QTemporaryDir>
#include <QtTest>

#include "core/importers.h"

using namespace wordmem;

namespace {
QString writeFile(const QTemporaryDir &dir, const QString &name,
                  const QString &content) {
    const QString p = dir.path() + QLatin1Char('/') + name;
    QFile f(p);
    f.open(QIODevice::WriteOnly | QIODevice::Truncate);
    f.write(content.toUtf8());
    f.close();
    return p;
}

QString meaningLabel(const QJsonObject &m) {
    const QString pos = m.value(QLatin1String("pos")).toString();
    const QString text = m.value(QLatin1String("meaning")).toString();
    return pos.isEmpty() ? text : pos + QLatin1Char(' ') + text;
}
}  // namespace

class TestImporters : public QObject {
    Q_OBJECT
private slots:
    void cleanFieldStripsAnkiMarkup();
    void parseDefinitionSplitsPos();
    void parseDefinitionWithoutPos();
    void dedupeKeepsFirst();
    void plainTextTabAndSpace();
    void csvEcdictAndGeneric();
    void wordmemJson();
    void simpleJsonArray();
    void jsonlLines();
    void autoRoutingByExtension();
    void unsupportedAndMissingFile();
};

void TestImporters::cleanFieldStripsAnkiMarkup() {
    const QString raw = QStringLiteral(
        "[sound:a.mp3]hello<br><b>world</b>&amp;<i>x</i>  y");
    QCOMPARE(cleanField(raw), QStringLiteral("hello world&x y"));
    // [sound:] 标记大小写不敏感
    QCOMPARE(cleanField(QStringLiteral("[SOUND:a.mp3] cat")),
             QStringLiteral("cat"));
    QCOMPARE(cleanField(QString()), QString());
}

void TestImporters::parseDefinitionSplitsPos() {
    const auto ms =
        parseDefinition(QStringLiteral("a. 彩色的；柔和的（bland）n. 蜡笔"));
    QCOMPARE(ms.size(), 2);
    QCOMPARE(ms.at(0).value(QLatin1String("pos")).toString(),
             QStringLiteral("a."));
    QCOMPARE(ms.at(0).value(QLatin1String("meaning")).toString(),
             QStringLiteral("彩色的；柔和的（bland）"));
    QCOMPARE(meaningLabel(ms.at(1)), QStringLiteral("n. 蜡笔"));
}

void TestImporters::parseDefinitionWithoutPos() {
    const auto ms = parseDefinition(QStringLiteral("苹果；一种水果"));
    QCOMPARE(ms.size(), 1);
    QVERIFY(ms.at(0).value(QLatin1String("pos")).toString().isEmpty());
    QCOMPARE(ms.at(0).value(QLatin1String("meaning")).toString(),
             QStringLiteral("苹果；一种水果"));
    QVERIFY(parseDefinition(QStringLiteral("   ")).isEmpty());
}

void TestImporters::dedupeKeepsFirst() {
    const QList<QJsonObject> words = {
        {{"word", "Apple"}, {"phonetic", "/ˈæpl/"}},
        {{"word", "apple"}, {"phonetic", ""}},
        {{"word", ""}, {"phonetic", ""}},
    };
    const auto out = dedupeWords(words);
    QCOMPARE(out.size(), 1);  // 空词丢弃、同词按小写去重
    QCOMPARE(out.at(0).value(QLatin1String("phonetic")).toString(),
             QStringLiteral("/ˈæpl/"));
}

void TestImporters::plainTextTabAndSpace() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString p = writeFile(
        dir, QStringLiteral("words.txt"),
        QStringLiteral("apple\tn. 苹果\nbanana 香蕉\n\ncherry\n"));
    const auto book = parseAuto(p);
    QVERIFY(book.has_value());
    QCOMPARE(book->words.size(), 2);  // 无分隔符的 cherry 被跳过
    QCOMPARE(book->words.at(0).value(QLatin1String("word")).toString(),
             QStringLiteral("apple"));
    QCOMPARE(book->words.at(1).value(QLatin1String("word")).toString(),
             QStringLiteral("banana"));
}

void TestImporters::csvEcdictAndGeneric() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());

    // ECDICT 路径：表头含 word + translation
    const QString p1 = writeFile(
        dir, QStringLiteral("ecdict.csv"),
        QStringLiteral("word,phonetic,translation\n"
                       "apple,/ˈæpl/,n. 苹果\n"
                       "\"cat\",\"/kæt/\",\"n. 猫；v. 猫科动物\"\n"));
    const auto b1 = parseCsv(p1);
    QVERIFY(b1.has_value());
    QCOMPARE(b1->words.size(), 2);
    QCOMPARE(b1->words.at(0).value(QLatin1String("phonetic")).toString(),
             QStringLiteral("/ˈæpl/"));
    const QJsonArray ms =
        b1->words.at(1).value(QLatin1String("meanings")).toArray();
    QCOMPARE(ms.size(), 2);  // 引号内分号切分词性
    QCOMPARE(meaningLabel(ms.at(1).toObject()), QStringLiteral("v. 猫科动物"));

    // 通用路径：前两列为 word/释义（无表头识别）
    const QString p2 = writeFile(dir, QStringLiteral("plain.csv"),
                                 QStringLiteral("apple,n. 苹果\n"
                                                "banana,n. 香蕉\n"));
    const auto b2 = parseCsv(p2);
    QVERIFY(b2.has_value());
    QCOMPARE(b2->words.size(), 2);
    QCOMPARE(b2->words.at(1).value(QLatin1String("word")).toString(),
             QStringLiteral("banana"));
}

void TestImporters::wordmemJson() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString p = writeFile(
        dir, QStringLiteral("book.json"),
        QStringLiteral(R"JSON({"book":{"name":"雅思词汇","description":"核心词"},
"words":[{"word":"apple","phonetic":"/ˈæpl/",
          "meanings":[{"pos":"n.","meaning":"苹果"}],
          "examples":[{"text":"an apple","trans":"一个苹果"}]},
         {"word":"APPLE","phonetic":"","meanings":[],"examples":[]}]})JSON"));
    const auto book = parseWordmemJson(p);
    QVERIFY(book.has_value());
    QCOMPARE(book->name, QStringLiteral("雅思词汇"));
    QCOMPARE(book->description, QStringLiteral("核心词"));
    QCOMPARE(book->words.size(), 1);  // 大小写重复被去重
    const QJsonArray es =
        book->words.at(0).value(QLatin1String("examples")).toArray();
    QCOMPARE(es.size(), 1);
    // trans 字段被规整为 translation
    QCOMPARE(es.at(0).toObject().value(QLatin1String("translation")).toString(),
             QStringLiteral("一个苹果"));
}

void TestImporters::simpleJsonArray() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString p = writeFile(
        dir, QStringLiteral("simple.json"),
        QStringLiteral(R"JSON([{"word":"cat","phonetic":"/kæt/",
"translations":[{"type":"n","translation":"猫"},{"type":"vt","translation":"殴打"}],
"phrases":[{"phrase":"a cat","translation":"一只猫"},
           {"phrase":"p2","translation":"t2"},{"phrase":"p3","translation":"t3"},
           {"phrase":"p4","translation":"t4"}]}])JSON"));
    const auto book = parseSimpleJson(p);
    QVERIFY(book.has_value());
    QCOMPARE(book->words.size(), 1);
    const QJsonObject w = book->words.at(0);
    QCOMPARE(w.value(QLatin1String("word")).toString(), QStringLiteral("cat"));
    const QJsonArray ms = w.value(QLatin1String("meanings")).toArray();
    QCOMPARE(ms.size(), 2);
    QCOMPARE(ms.at(0).toObject().value(QLatin1String("pos")).toString(),
             QStringLiteral("n."));  // type 补上 '.' 后缀
    QCOMPARE(meaningLabel(ms.at(1).toObject()), QStringLiteral("vt. 殴打"));
    const QJsonArray es = w.value(QLatin1String("examples")).toArray();
    QCOMPARE(es.size(), 3);  // 短语只取前 3 个
    QCOMPARE(es.at(0).toObject().value(QLatin1String("text")).toString(),
             QStringLiteral("a cat"));
}

void TestImporters::jsonlLines() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString content = QStringLiteral(
        "{\"word\":\"dog\",\"translations\":[{\"type\":\"n\","
        "\"translation\":\"狗\"}]}\n"
        "{\"word\":\"bird\",\"translations\":[{\"type\":\"n\","
        "\"translation\":\"鸟\"}]}\n");
    const QString p = writeFile(dir, QStringLiteral("words.jsonl"), content);
    const auto book = parseAuto(p);
    QVERIFY(book.has_value());
    QCOMPARE(book->words.size(), 2);

    // .json 扩展名但实为 JSONL：parse_auto 应回退 simple 解析
    const QString p2 = writeFile(dir, QStringLiteral("as_json.json"), content);
    const auto book2 = parseAuto(p2);
    QVERIFY(book2.has_value());
    QCOMPARE(book2->words.size(), 2);
}

void TestImporters::autoRoutingByExtension() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const auto txt = parseAuto(
        writeFile(dir, QStringLiteral("a.txt"), QStringLiteral("cat\tn. 猫")));
    QVERIFY(txt.has_value());
    QCOMPARE(txt->words.size(), 1);

    const auto csv = parseAuto(writeFile(dir, QStringLiteral("a.csv"),
                                         QStringLiteral("cat,n. 猫")));
    QVERIFY(csv.has_value());
    QCOMPARE(csv->words.size(), 1);

    // 显式 fmt 走指定 parser（txt 内容用 csv parser 也能解析）
    const auto forced = parseCsv(writeFile(dir, QStringLiteral("b.txt"),
                                           QStringLiteral("dog,n. 狗")));
    QVERIFY(forced.has_value());
    QCOMPARE(forced->words.at(0).value(QLatin1String("word")).toString(),
             QStringLiteral("dog"));
}

void TestImporters::unsupportedAndMissingFile() {
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString p = writeFile(dir, QStringLiteral("book.xyz"),
                                QStringLiteral("whatever"));
    QString err;
    QVERIFY(!parseAuto(p, &err).has_value());
    QVERIFY(err.contains(QStringLiteral("不支持")));

    QString err2;
    QVERIFY(!parseAuto(dir.path() + QStringLiteral("/nope.json"), &err2)
                 .has_value());
    QVERIFY(!err2.isEmpty());
}

QTEST_GUILESS_MAIN(TestImporters)
#include "test_importers.moc"
