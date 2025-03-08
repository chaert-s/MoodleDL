# 🎓 MoodleDL

[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An easy way to bulk download content from Moodle.

## ✨ Features

- **Complete Course Downloads**: Gets resources, assignments, folders, and other content
- **Smart Handling**: Detects different Moodle versions and themes
- **Resume Support**: Skip already downloaded files
- **Progress Tracking**: Visual progress bars for downloads
- **Flexible Selection**: Choose which courses to download
- **File Organization**: Content is neatly organized by course and section

## 📋 Requirements

- Python 3.6 or higher
- Packages: `requests`, `beautifulsoup4`, `tqdm`

## 🚀 Installation

1. Clone this repository or download the script:

```bash
git clone https://github.com/yourusername/moodle-downloader.git
```

2. Install required packages:

```bash
pip install requests beautifulsoup4 tqdm
```

## 💡 Usage

### Basic Usage

```bash
python moodle_downloader.py -u https://moodle.university.edu
```

You'll be prompted for your username and password, and then shown a list of available courses.

### Command Line Arguments

```bash
python moodle_downloader.py -u https://moodle.university.edu -n username -p password -d /path/to/download/folder
```

| Argument | Description |
|----------|-------------|
| `-u`, `--url` | **Required.** Your Moodle instance URL |
| `-n`, `--username` | Your Moodle username (will be prompted if not provided) |
| `-p`, `--password` | Your Moodle password (will be prompted if not provided) |
| `-d`, `--directory` | Download directory (defaults to ~/Downloads/MoodleContent) |
| `-q`, `--quiet` | Quiet mode with less output |
| `-f`, `--force` | Force re-download of existing files |

## ⚠️ Important Note

If your courses aren't appearing correctly, **favorite your courses on your Moodle dashboard** before running the downloader. This ensures the tool can find all your courses properly.

To favorite courses:
1. Log in to your Moodle dashboard
2. Find the courses you want to download via "My Courses" and star them
3. Run the downloader again

## 📂 Output Structure

Downloads are organized in the following structure:

```
MoodleContent/
├── Course 1/
│   ├── Section 1/
│   │   ├── document.pdf
│   │   ├── Assignment 1/
│   │   │   ├── description.txt
│   │   │   └── assignment_file.docx
│   │   └── Folder 1/
│   │       └── content.pptx
│   └── Section 2/
│       └── ...
└── Course 2/
    └── ...
```

## 🔍 Troubleshooting

### Common Issues

- **Login Problems**: Verify your credentials and Moodle URL. Some institutions use custom authentication methods that may not be compatible.
- **Missing Courses**: Make sure to favorite your courses on your Moodle dashboard.
- **SSL Errors**: If you encounter SSL verification errors, update your Python packages: `pip install --upgrade requests certifi`.
- **Permission Errors**: Ensure you have write permissions to the download directory.

### Debug Mode

When the downloader can't extract a file from a resource page, it saves the HTML content for debugging. Check these files if some resources aren't downloading properly.

## 💻 How It Works

The downloader:

1. Logs in to your Moodle account
2. Identifies available courses
3. For each selected course:
   - Extracts all sections
   - Finds and downloads resources
   - Processes folder modules
   - Extracts assignment information and attachments
4. Organizes everything in a structured directory

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
