# TreeLine Development Guide

## Running the Application
- Run application: `python3 treeline.py [--lang LANG] [filename ...]`
- Build standalone executable: 
  - PyInstaller: `pyinstaller treeline.spec`
  - cx_Freeze: `python setup.py build`

## Code Style Guidelines
- **Naming Conventions**:
  - Classes: CamelCase (`TreeMainControl`, `ConfigDialog`)
  - Methods/Variables: snake_case (`update_tools`, `file_path_obj`)
  - Translation functions use leading underscore (`_()`)
- **Imports**: Group by type - standard library, PyQt5, then local imports
- **Error Handling**: Use specific exceptions with user-friendly messages
- **Docstrings**: Google-style with function description and argument details
- **Project Structure**: Modular design with class-based architecture
- **No Type Hints**: Codebase doesn't use typing annotations

## Technologies
- GUI Framework: PyQt5
- Python 3.x compatible
- Supports file operations, multilingual UI, encryption, and compression

## Development Process
- When modifying files, maintain existing style conventions
- Test any UI changes across different platforms if possible
- Verify changes work with various file formats supported by the application

## Output File Format
 - documentation.trln is an example of an output format saved by TreeLine
 - every new feature implementation affecting the data structure will need to    be saved in that format

