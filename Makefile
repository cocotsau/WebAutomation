PY := .venv/bin/python
PIP := .venv/bin/pip
# 阿里云： https://mirrors.aliyun.com/pypi/simple
# 华为云： https://repo.huaweicloud.com/repository/pypi/simple
# 清华源： https://pypi.tuna.tsinghua.edu.cn/simple
MIRROR := https://mirrors.aliyun.com/pypi/simple
PIP_INSTALL := $(PIP) install -i $(MIRROR)

.PHONY: venv install api cli desktop test

venv: .venv/bin/python

.venv/bin/python:
	python3 -m venv .venv
	$(PIP_INSTALL) -U pip

install: venv
	$(PIP_INSTALL) -r requirements.txt

api: venv
	$(PY) -m src.app api

cli: venv
	$(PY) -m src.app cli $(ARGS)

desktop: venv
	$(PY) -m src.app desktop

test: venv
	$(PY) -m unittest -q tests/test_basic.py
