#!/bin/bash
#
# Clean the dir tree of backup and compiled files before doing a checkin.
#

REGEX="(^.*.pyc$)|(^.*.wsgic$)|(^.*~$)|(.*#$)" #|(.*\.log((.*)(\d)+)?)"
CMD="find . -regextype posix-egrep -regex $REGEX"

if [ "$1" == "clean" ]; then
    $CMD -exec rm {} \;
else
    $CMD
fi
