#!/bin/bash
echo "🔑 Source Line Count in current dir"
find . -name "*.py" -exec wc -l {} + | sort -n