# -*- coding: utf-8 -*-
"""支持 `python -m wordmem` 方式启动。"""
import sys

from wordmem.app import main

if __name__ == "__main__":
    sys.exit(main())
