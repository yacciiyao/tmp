# -*- coding: utf-8 -*-
# @File: test.py
# @Author: yaccii
# @Time: 2025-12-19 13:18
# @Description:
import os
print("HTTP_PROXY=", os.environ.get("HTTP_PROXY"))
print("HTTPS_PROXY=", os.environ.get("HTTPS_PROXY"))
print("NO_PROXY=", os.environ.get("NO_PROXY"))

from elasticsearch import Elasticsearch
es = Elasticsearch("http://47.120.70.119:19200")
print(es.info())