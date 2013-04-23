# Makefile for building cothread documentation

RST2HTML = rst2html

SOURCE_FILES = $(wildcard *.rst)

HTML_FILES = $(patsubst %.rst, %.html, $(SOURCE_FILES))

default: $(HTML_FILES)

clean:
	rm -f *.html

%.html: %.rst
	$(RST2HTML) $^ >$@

