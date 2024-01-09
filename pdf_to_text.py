import os
import PyPDF2
import argparse

def pdf_to_text(pdf_path):
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text() + '\n' if page.extract_text() else ''
    return text

def convert_pdfs_in_directory(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.pdf'):
            pdf_path = os.path.join(directory, filename)
            text = pdf_to_text(pdf_path)
            text_filename = os.path.splitext(pdf_path)[0] + '.txt'
            with open(text_filename, 'w') as text_file:
                text_file.write(text)
            print(f"Converted '{filename}' to text.")

def main():
    parser = argparse.ArgumentParser(description='Convert PDF files in a directory to text files.')
    parser.add_argument('directory', type=str, help='Directory containing PDF files')
    
    args = parser.parse_args()
    convert_pdfs_in_directory(args.directory)

if __name__ == '__main__':
    main()
