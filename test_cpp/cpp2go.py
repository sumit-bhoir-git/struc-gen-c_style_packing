import re, sys, os

def cpp_to_go_structs(cpp_file, go_file, pack=2):
    type_map = {
        'uint8_t': 'uint8',
        'int8_t': 'int8',
        'int16_t': 'int16',
        'uint16_t': 'uint16',
        'int32_t': 'int32',
        'uint32_t': 'uint32',
        'int64_t': 'int64',
        'uint64_t': 'uint64',
        'char': 'byte',
        'unsigned char': 'byte',
        'short': 'int16',
        'unsigned short': 'uint16',
        'int': 'int',
        'unsigned int': 'uint',
        'long': 'int64',
        'unsigned long': 'uint64',
        'long long': 'int64',
        'unsigned long long': 'uint64',
        'float': 'float32',
        'double': 'float64',
        'bool': 'bool'
    }

    with open(cpp_file) as f:
        cpp = f.read()

    structs = re.findall(r'struct\s+(\w+)\s*{([^}]*)}', cpp)

    with open(go_file, 'w') as f:
        f.write('package main\n\n')
        for name, body in structs:
            f.write(f'//go:generate struc-gen -little -pack {pack}\n')
            f.write(f'type {name} struct {{\n')
            for line in body.splitlines():
                line = line.strip().rstrip(';')
                if not line:
                    continue
                parts = line.split()
                if len(parts) == 2:
                    t, v = parts
                elif len(parts) == 3:
                    t = parts[0] + ' ' + parts[1]
                    v = parts[2]
                else:
                    t, v = parts[0], parts[-1]
                go_t = type_map.get(t, t)
                # Fix for array fields: insert space between name and type
                array_match = re.match(r'(\w+)\[(\d+)\]', v)
                if array_match:
                    field_name = array_match.group(1)
                    arr_len = array_match.group(2)
                    f.write(f'\t{field_name} [{arr_len}]{go_t}\n')
                else:
                    f.write(f'\t{v} {go_t}\n')
            f.write('}\n\n')

def cpp_value_to_go(val):
    val = val.strip()
    # If it's a char literal, convert to ASCII integer
    if re.match(r"^'.'$", val):
        # Use Python's string decoding for escape sequences
        char = val[1:-1]  # strip the quotes
        # Handle escape sequences like '\0', '\n', etc.
        if char.startswith('\\'):
            # Use Python's unicode_escape to decode
            char = char.encode().decode('unicode_escape')
        return str(ord(char))
    val = val.replace('LL','').replace('U','')
    return val

def parse_initializations(cpp):
    # Find lines like: Example e = {1, 2, 3, 4, 1234567890LL};
    inits = re.findall(r'(\w+)\s+\w+\s*=\s*{([^}]*)}', cpp)
    result = {}
    for name, values in inits:
        vals = [cpp_value_to_go(v) for v in values.split(',')]
        result[name] = vals
    return result

def get_struct_fields(structs, struct_name):
    for name, body in structs:
        if name == struct_name:
            return [line.strip().rstrip(';').split()[1] for line in body.splitlines() if line.strip()]
    return []

def get_struct_types(structs, struct_name):
    for name, body in structs:
        if name == struct_name:
            return [line.strip().rstrip(';').split()[0] for line in body.splitlines() if line.strip()]
    return []

def is_array_field(field_type):
    return re.match(r'.*\[\d+\]$', field_type)

def array_length(field_type):
    m = re.match(r'.*\[(\d+)\]$', field_type)
    return int(m.group(1)) if m else 0

def generate_go_test(cpp_file, go_file, bin_file="sample_cpp.bin"):
    with open(cpp_file) as f:
        cpp = f.read()
    structs = re.findall(r'struct\s+(\w+)\s*{([^}]*)}', cpp)
    inits = parse_initializations(cpp)
    top_level = re.findall(r'(\w+)\s+\w+\s*=\s*{[^}]*};', cpp)
    test_file = os.path.splitext(go_file)[0] + "_test.go"
    with open(test_file, 'w') as f:
        f.write('package main\n\nimport (\n\t"os"\n\t"testing"\n\t"bytes"\n)\n\n')
        f.write('func TestInteropWithCpp(t *testing.T) {\n')
        f.write(f'\tdata, err := os.ReadFile("{bin_file}")\n')
        f.write('\tif err != nil {\n\t\tt.Fatalf("Failed to read C++ binary: %v", err)\n\t}\n')
        f.write('\toffset := 0\n')
        for idx, name in enumerate(top_level):
            f.write(f'\tvar s{name} {name}\n')
            if idx == 0:
                f.write(f'\tn := s{name}.UnmarshalBinary(data[offset:])\n')
            else:
                f.write(f'\tn = s{name}.UnmarshalBinary(data[offset:])\n')
            f.write(f'\tif n == 0 {{\n\t\tt.Fatalf("UnmarshalBinary {name} failed")\n\t}}\n')
            # Field checks
            if name in inits:
                vals = inits[name]
                fields = get_struct_fields(structs, name)
                types = get_struct_types(structs, name)
                checks = []
                val_idx = 0
                for field, typ in zip(fields, types):
                    if typ in [n for n, _ in structs]:  # Embedded struct
                        subfields = get_struct_fields(structs, typ)
                        subtypes = get_struct_types(structs, typ)
                        for subfield, subtype in zip(subfields, subtypes):
                            if is_array_field(subtype):
                                length = array_length(subtype)
                                arr_vals = vals[val_idx:val_idx+length]
                                for i, arr_val in enumerate(arr_vals):
                                    checks.append(f's{name}.{field}.{subfield}[{i}] != {arr_val}')
                                val_idx += length
                            else:
                                go_val = cpp_value_to_go(vals[val_idx])
                                checks.append(f's{name}.{field}.{subfield} != {go_val}')
                                val_idx += 1
                    elif is_array_field(typ):
                        length = array_length(typ)
                        arr_vals = vals[val_idx:val_idx+length]
                        for i, arr_val in enumerate(arr_vals):
                            checks.append(f's{name}.{field}[{i}] != {arr_val}')
                        val_idx += length
                    else:
                        go_val = cpp_value_to_go(vals[val_idx])
                        checks.append(f's{name}.{field} != {go_val}')
                        val_idx += 1
                cond = ' || '.join(checks)
                f.write(f'\tif {cond} {{\n\t\tt.Errorf(\"{name} mismatch: %+v\", s{name})\n\t}}\n')
            f.write(f'\toffset += n\n')
        f.write('}\n')

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 cpp2go.py <cpp_file> <go_file> [--test]")
        sys.exit(1)

    cpp_file = sys.argv[1]
    go_file = sys.argv[2]

    if "--test" in sys.argv:
        generate_go_test(cpp_file, go_file)
    else:
        cpp_to_go_structs(cpp_file, go_file)