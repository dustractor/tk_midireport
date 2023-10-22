# tk_midireport
using mido to scan midi files into a database to be able to search by key and/or number of notes.

By default it looks for files in C:/Users/\<username>/Documents/Image-Line/FL Studio/Presets/Scores but that can be changed by passing a different directory as the ``--rootdir`` parameter.

Use the ``--scan`` flag to cause it to do the actual scan. (This is so that it doesn't scan every time you launch.)

Files can be filtered by their (purported) key signature and the number of notes.

Files with zero notes tend to be tuning files.

Most files do not have a key signature and the majority of those that do are lying about their key signature. I plan to eventually implement heuristics for guessing key and mode, as well as highlighting files that lie about their key, and ultimately provide a function to update the files with accurate key signature information.

As for now, you get to double-click the files on the list it will pop open an explorer window with the file selected.

Or you can select multiple (hold shift) and press control+. and it will ask you for a folder and then copy the selected files to that folder.
