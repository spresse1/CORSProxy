#!/bin/bash

if [ ! -e "$1" ]
then
    echo "Input file must exist!"
    exit 1
fi

pylint --disable=all -e $(grep enabled "$1" | grep -Eio 'pylint_[[:alnum:]]{5}' | sed 's/PyLint_/-e /' | xargs) --generate-rcfile | tee $(dirname $0)/.pylintrc
