.PHONY: check syntax test smoke checksum

check: syntax test smoke

syntax:
	fish --no-config -n ./lns

test:
	PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v

smoke:
	test -x ./lns
	./lns --help >/dev/null

checksum:
	shasum -a 256 ./lns
