# check-time-machine
Python script for checking to make sure all of your files are actually backed up by Time Machine, and offers options for fixing files that are not.

### Usage

```python checktimemachine.py [path to directory]```

If a directory is not specified, checktimemachine.py will scan the entire filesystem of all of the volumes included in latest Time Machine backup and compare to the files contained with that backup.

If a directory is specified, will scan just that directory and compare to its latest backup.

Any missing files will be presented in two lists:
  1. Non-excluded files that are missing: files that are not marked by Time Machine as being excluded but are nevertheless not in your Time Machine backup. This could be because they simply haven't been backed up yet, or it could be because Time Machine has been very naughty and skipped over these files for no good reason.
  2. Excluded files: files that are marked by Time Machine as being excluded, either by sticky exclusion or fixed-path exclusion. (See ```man tmutil``` for more information.)

Will then offer to add excluded files to the Time Machine backup, and to "wiggle" the files the non-excluded files that are not backed up. And by wiggle, I mean it will ```touch``` the file, ```touch``` its containing directory, rename the file, and then rename it back to its original name. Note: this is not guaranteed to accomplish anything, but some users have reported that it helps.

## Important notes!

This script will automatically ignore a wide variety of files and folders that, as far as I can tell, are not supposed to be included in a Time Machine backup. This list was created by running the script and seeing what miscellaneous files it finds that I don't care about.

At the top of the script are several lists. Before running this script, you should consider reviewing them and adding any paths you want ignored or remove any paths that are important to you. They are:
  1. ```excludeDirectories```: Directories that have sticky exclusion that I'm pretty sure are safe to ignore.
  2. ```excludeFiles```: Files that have sticky exclusion that I'm also pretty sure are safe to ignore.
  3. ```excludeExtensions```: List of extensions that will be ignored. Can apply to any file or folder.
  4. ```userIgnore```: Files and folders that I personally wanted to ignore but you may feel differently about it. Definitely should review this one.

Please pay close attention to the comments for each of these variables, as they describe what format the paths have to be in and how they are applied.

The script will also ignore anything that would already by excluded by Time Machine based on the contents of the StdExclusions.plist file in the System folder.
