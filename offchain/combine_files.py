import os
import sys

def combine_files(input_folder, output_file):
    with open(output_file, 'w', encoding='utf-8') as outfile:
        for filename in os.listdir(input_folder):
            filepath = os.path.join(input_folder, filename)

            # Skip directories
            if not os.path.isfile(filepath):
                continue

            # Read file contents
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as infile:
                content = infile.read()

            # Write bracketed section to output
            outfile.write(f"[BEGIN: {filename}]\n")
            outfile.write(content)
            outfile.write(f"\n[END: {filename}]\n\n")

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <input_folder> <output_file>")
        sys.exit(1)

    input_folder = sys.argv[1]
    output_file = sys.argv[2]

    if not os.path.isdir(input_folder):
        print(f"Error: '{input_folder}' is not a valid directory.")
        sys.exit(1)

    combine_files(input_folder, output_file)
    print(f"Combined file written to: {output_file}")

if __name__ == "__main__":
    main()
