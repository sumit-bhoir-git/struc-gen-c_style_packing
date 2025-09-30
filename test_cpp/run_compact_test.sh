#!/bin/bash
# filepath: /run_compat_test.sh
set -e

# Usage: ./run_compat_test.sh <cpp_file> <go_file> [output_dir]
CPP_FILE="$1"
GO_FILE="$2"
OUTPUT_DIR="${3:-$(dirname "$CPP_FILE")}"

if [ -z "$CPP_FILE" ] || [ -z "$GO_FILE" ]; then
    echo "Usage: $0 <cpp_file> <go_file> [output_dir]"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

python3 cpp2go.py "$CPP_FILE" "$OUTPUT_DIR/$(basename $GO_FILE)"
python3 cpp2go.py "$CPP_FILE" "$OUTPUT_DIR/$(basename $GO_FILE)" --test
go generate "$OUTPUT_DIR/$(basename $GO_FILE)"
g++ -o "$OUTPUT_DIR/cpp_writer" "$CPP_FILE"
pushd "$OUTPUT_DIR" > /dev/null
./cpp_writer
popd > /dev/null
GO_TEST_FILE="$OUTPUT_DIR/$(basename "${GO_FILE%.*}_test.go")"
go test -v "$GO_TEST_FILE" "$OUTPUT_DIR/$(basename $GO_FILE)" "$OUTPUT_DIR/$(basename "${GO_FILE%.*}_gen.go")"
