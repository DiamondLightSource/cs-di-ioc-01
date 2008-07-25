# Mostly dummy makefile so that automated install is happy.

default: docs

clean:
	rm *.pyc
	make -C docs clean

docs:
	make -C docs

.PHONY: docs
