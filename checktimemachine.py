from __future__ import division
import os
from pprint import pprint
import types
from subprocess import Popen, PIPE, call
from ast import literal_eval
import sys
import time
import uuid
import plistlib

# Directories that have "sticky exclusions".
# You may want to review these and make sure you truly don't want
# their contents being backed up. That said, these all seem pretty
# safe to ignore.
# NOTE: these are not absolute paths. Any directory whose absolute
# path ends in any of these strings will be ignored.
excludeDirectories = ["/DerivedData",
                      "/.Trash",
                      "/iTunes/Album Artwork/Cache",
                      "/iTunes/Album Artwork/Generated",
                      "/iTunes/Album Artwork/Store",
                      "/iTunes/Album Artwork/Editorial",
                      "/Library/LanguageModeling",
                      "/Library/Logs",
                      "/Library/Caches",
                      "/Calendars/Calendar Cache",
                      "/Dictionaries/JapaneseInputMethod",
                      "/Library/Saved Application State",
                      "/Developer/CoreSimulator/Devices",
                      "/Developer/Xcode/UserData/IB Support/Simulator Devices",
                      "/Library/iTunes/iPod Software Updates",
                      "/Library/iTunes/iPhone Software Updates",
                      "/Library/iTunes/iPad Software Updates",
                      "Photos Library.photoslibrary/Database"]

# Files that have "sticky exclusion"
# You may want to review these and make sure you truly don't want
# their contents being backed up. That said, these all seem pretty
# safe to ignore.
# NOTE: these are not absolute paths. Any file whose absolute path
# ends in any of these strings will be ignored.
excludeFiles = ["iTunes/iTunes Library.xml",
                "iTunes/iTunes Music Library.xml",
                "iTunes/iTunes Music Library Backup.xml",
                "Chrome/Default/History-journal",
                "Chrome/Default/Favicons-journal",
                "Chrome/Default/Favicons",
                "Chrome/Default/History",
                "Chrome/Safe Browsing Download",
                "Chrome/Safe Browsing UwS List",
                "Chrome/Safe Browsing Download Whitelist",
                "Chrome/Safe Browsing IP Blacklist",
                "Chrome/Safe Browsing Inclusion Whitelist",
                "Chrome/Safe Browsing Extension Blacklist",
                "Chrome/Safe Browsing UwS List Prefix Set",
                "Chrome/Safe Browsing Bloom",
                "Chrome/Safe Browsing Csd Whitelist",
                "Chrome/Safe Browsing Bloom Prefix Set",
                "Chrome/Safe Browsing Bloom Filter 2",
                "Library/Safari/WebpageIcons.db",
                "Library/Safari/HistoryIndex.sk",
                "Library/Calendars/Calendar Cache",
                "V3/MailData/Envelope Index",
                "/private/etc/resolv.conf",
                "/private/etc/kcpassword",
                "/.hotfiles.btree"]

# Exclude all files and folders with these extensions
# ...Is .db-journal safe to exclude consistently?
excludeExtensions = [".db-journal",
                     ".nobackup"]

# Files and directories with "sticky exclusion" that I (Brian) don't
# care about from my own system. I personally think it's probably 
# okay to ignore these, but you may disagree.
# NOTE: once again these are not absolute paths. Any file or directory
# whose absolute path ends in any of these strings will be ignored.
userIgnore = ["/Photos Library.photoslibrary/database",
              "/Library/Containers/com.apple.cloudphotosd/Data",
              "/Library/Application Support/CloudDocs",
              "/.Trashes",
              "/private/var/db/CoreDuet",
              "/Pictures/iPhoto Library/iPod Photo Cache",
              "/iPhoto Library/Database/apdb/BigBlobs.apdb",
              "/iPhoto Library/Database/BigBlobs.apdb",
              "/iPhoto Library/iPod Photo Cache",
              "/iPhoto Library/AlbumData.xml",
              "/Pictures/iPod Photo Cache",
              "/Library/Mail/V2/MailData/AvailableFeeds",
              "/Library/Mail/V2/MailData/BackingStoreUpdateJournal",
              "/Library/Mail/V2/MailData/Envelope Index-shm",
              "/Library/Mail/V2/MailData/Envelope Index-wal",
              "/Library/Mail/V2/MailData/Envelope Index",
              "/Library/Application Support/iDVD/Installed Themes",
              "/Users/Shared/adi",
              "/Application Support/Microsoft/PlayReady",
              "Vivaldi/Default/Favicons-journal",
              "Vivaldi/Default/Favicons",
              "Vivaldi/Default/History",
              "Vivaldi/Default/History-journal",]

excludePaths = []
excludeUserPaths = []

class myError(Exception):
    pass

class tmutilError(myError):
    pass

class pathError(myError):
    pass
    
class fileIOError(myError):
    pass

def getSystemVolume():
    dirs = os.listdir('/Volumes')
    
    for dir in dirs:
        path = os.path.join('/Volumes', dir)
        if os.path.islink(path) and os.path.realpath(path) == '/':
            return dir
    
    raise Exception('Could not determine the system volume')

def pathToVolumeAndRelativePath(path):
    """For the given path, returns the volume containing the path, and a normalized
    path relative to the root of its volume"""
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    
    if path.endswith('/'):
        path = path[:-1]
    
    if not os.path.exists(path):
        raise pathError('Not found: %s' % path)
    
    if not os.path.isdir(path):
        raise pathError('Path must be to a directory')
    
    if not path.startswith('/Volumes'):
        return getSystemVolume(), path[1:]
    
    parts = path.split('/')
    
    if len(parts) < 3:
        raise pathError('Invalid path: %s' % path)
    
    return parts[2], '/'.join(parts[3:])

def printOverlapping(text):
    sys.stdout.write('\r%s      ' % text)
    sys.stdout.flush()

excludeAbsolutePathsSetByUser = ()

def getSkipPaths():
    p = Popen(['defaults', 'read', '/Library/Preferences/com.apple.TimeMachine.plist', 'SkipPaths'], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    
    if p.returncode != 0:
        raise Exception("defaults error! Couldn't get time machine preferences: " + err)
    
    return literal_eval(out)

excludeAbsolutePathsSetByUser = getSkipPaths()

def latestBackup():
    p = Popen(['tmutil', 'latestbackup'], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    
    if p.returncode != 0:
        raise tmutilError('tmutil error! ' + err)
    
    return out.strip()

def fileIsIntentionallyExcluded(path):
    p = Popen(['tmutil', 'isexcluded', path], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    
    if p.returncode != 0:
        raise tmutilError('tmutil error! ' + err)
    
    if out.startswith('[Included]'):
        return False
    elif out.startswith('[Excluded]'):
        return True
    else:
        raise tmutilError('Unexpected output from tmutil! ' + out)

def shouldExcludeFileOrDirectory(absolutePath, item, inHomeDir, homePath):
    if inHomeDir and os.path.join(homePath, item) in excludeUserPaths:
        return True
    
    for extension in excludeExtensions:
        if absolutePath.endswith(extension):
            return True
    
    for path in userIgnore:
        if absolutePath.endswith(path):
            return True
    
    return False

def shouldExcludeDirectory(volumeRelativePath, absolutePath):
    if volumeRelativePath in excludePaths or absolutePath in excludeAbsolutePathsSetByUser:
        return True
    
    for dir in excludeDirectories:
        if absolutePath.endswith(dir):
            return True
            
    return False

def shouldExcludeFile(absolutePath):
    for filename in excludeFiles:
        if absolutePath.endswith(filename):
            return True
    
    return False

def isMetaDataFile(item):
    return item.startswith('._')

srcTotalFiles = 0

def incrementSrcTotalFiles():
    global srcTotalFiles
    srcTotalFiles += 1
    
    if srcTotalFiles%5000 == 0:
        printOverlapping("...found %s" % srcTotalFiles)

def fileData(volumePath, path, isSrc=False):
    totalFiles = [0]
    lastPercent = [0]
    
    if isSrc:
        print "Getting list of files from source volume..."
    else:
        print "Getting list of files from Time Machine backup..."
    
    if not os.path.exists(os.path.join(volumePath, path)):
        if isSrc:
            raise fileIOError('Error: "%s" does not exist on disk. Cannot continue!' % path)
        else:
            raise fileIOError('Error: "%s" does not exist in Time Machine backup. Cannot continue!' % path)
    
    def determineInHomeDir(path):
        if path.startswith('Users/'):
            parts = path.split('/')
            
            if len(parts) > 1 and parts[1] != 'Shared':
                return True, '/'.join(parts[2:])
        
        return False, ""
    
    def incrementThisTotalFiles():
        totalFiles[0] += 1
        
        if srcTotalFiles > 0:
            percent = totalFiles[0]*100 // srcTotalFiles
        else:
            percent = 0
        
        if percent != lastPercent[0]:
            printOverlapping("...%s%%-ish complete" % percent)
            lastPercent[0] = percent
    
    if isSrc:
        incrementTotalFiles = incrementSrcTotalFiles
    else:
        incrementTotalFiles = incrementThisTotalFiles
    
    def fileDataRec(data, path):
        global srcTotalFiles
        
        inHomeDir, homePath = determineInHomeDir(path)
        
        
        for item in os.listdir(os.path.join(volumePath, path)):
            volumeRelativePath = os.path.join(path, item)
            absolutePath = os.path.join(volumePath, volumeRelativePath)
            
            if shouldExcludeFileOrDirectory(absolutePath, item, inHomeDir, homePath):
                continue
            
            if os.path.isdir(absolutePath) and not os.path.islink(absolutePath):
                if shouldExcludeDirectory(volumeRelativePath, absolutePath):
                    continue
                
                incrementTotalFiles()
                data['dirs'][item] = {'dirs': {}, 'files': set()}
                fileDataRec(data['dirs'][item], volumeRelativePath)
                
            elif os.path.isfile(absolutePath):
                # Need to check that this is a file since otherwise we will count sockets
                if shouldExcludeFile(absolutePath) or isMetaDataFile(item):
                    continue
                
                incrementTotalFiles()
                data['files'].add(item)
    
    result = {'dirs': {}, 'files': set()}
    fileDataRec(result, path)
    print "\nDone"
    return result

def numberOfItemsInDir(dir, path=''):
    return len(dir['dirs']) + len(dir['files']) + sum([numberOfItemsInDir(dir['dirs'][subdir]) for subdir in dir['dirs']])

def compare(srcFiles, dstFiles):
    count = [0]
    lastPercent = [0]
    print ""
    
    def incrementCountBy(x):
        count[0] += x
        
        if srcTotalFiles > 0:
            percent = count[0]*100 // srcTotalFiles
        else:
            percent = 0
        
        if percent != lastPercent[0]:
            printOverlapping("Comparing, %s%% complete" % percent)
            lastPercent[0] = percent
        
    def compareRec(result, src, dst, path):
        missing = []
        
        for dir in src['dirs']:
            if dir not in dst['dirs']:
                missing.append(os.path.join(path, dir) + '/')
                incrementCountBy(numberOfItemsInDir(src['dirs'][dir]))
            else:
                compareRec(result, src['dirs'][dir], dst['dirs'][dir], os.path.join(path, dir))
                
        incrementCountBy(len(src['dirs']))
        
        for file in src['files']:
            if file not in dst['files']:
                missing.append(os.path.join(path, file))
        
        incrementCountBy(len(src['files']))
        
        missingCount = len(missing)
        
        if missingCount > 0 and missingCount == len(src['files'])+len(src['dirs']):
            result += [os.path.join(path, file) for file in src['dirs'].keys()]
            result += [os.path.join(path, file) for file in src['files']]
        else:
            result += missing
    
    result = []
    compareRec(result, srcFiles, dstFiles, '')
    print "\nDone"
    return result

def findMissingFilesInFolder(targetVolume, targetPath):
    """Returns a list of files missing from the Time Machine backup
    targertVolume: the volume to check
    targetPath: the directory whose contents should be checked, specified
                as a relative path to the root of targetVolume"""
    global srcTotalFiles
    srcTotalFiles = 0
    
    if os.path.islink(os.path.join('/Volumes', targetVolume)):
        srcVolumePath = '/'
    else:
        srcVolumePath = os.path.join('/Volumes', targetVolume)
    
    srcFiles = fileData(srcVolumePath, targetPath, isSrc=True)
    dstFiles = fileData(os.path.join(latestBackup(), targetVolume), targetPath)

    missing = compare(srcFiles, dstFiles)
    
    return [os.path.join(srcVolumePath, targetPath, file) for file in missing]

def findAndPrintMissingFilesInAllVolumes():
    """Returns a list of all files that are missing from the Time Machine
    backup across all volumes."""
    result = []
    latestBackupRoot = os.path.join(latestBackup())
    
    for volume in os.listdir(latestBackupRoot):
        if volume.startswith('.'):
            continue
        
        print "*** Checking volume: %s" % volume
        result += findMissingFilesInFolder(volume, '')

    return result

def determinedExcluded(files):
    excluded = []
    included = []
    
    print "Determining which files are marked as excluded..."
    lastPercent = 0
    
    for i, file in enumerate(files):
        try:
            exclusion = fileIsIntentionallyExcluded(file)
        except tmutilError:
            print "Something went wrong with file: %s" % file
            continue
        
        if exclusion:
            excluded.append(file)
        else:
            included.append(file)
        
        percent = ((i+1)*100) // len(files)
        
        if percent != lastPercent:
            printOverlapping("...%s%% complete" % percent)
            lastPercent = percent
    
    return excluded, included

def printResults(excluded, included):
    print "\nNon-excluded files not yet in backup, or missing from backup:"
    
    if len(included) > 0:
        for file in included:
            print "  %s" % file
    else:
        print "  (none)"

    print "\nExcluded files:"
    
    if len(excluded) > 0:
        for file in excluded:
            print "  %s" % file
    else:
        print "  (none)"

def addToTimeMachineBackup(file):
    print "Adding to backup: %s" % file
    p = Popen(['tmutil', 'removeexclusion', file], stdout=PIPE, stderr=PIPE)
    out, err = p.communicate()
    
    if p.returncode != 0:
        print "Error! Failed to add: %s" % file
        print "tmutil stderr:"
        print err
        print "\n"
    
    if fileIsIntentionallyExcluded(file):
        print "Error: file is still excluded???"

def tryToFixMissingFile(file):
    if file.endswith('/'):
        file = file[:-1]
    
    print "Touching: %s" % file
    call(["touch", file])
    
    print "Touching: %s" % os.path.dirname(file)
    call(["touch", os.path.dirname(file)])
    
    print "Temporarily changing name of: %s" % file
    newPath = os.path.join(os.path.dirname(file), os.path.basename(file) + '_' + str(uuid.uuid4()))
    
    try:
        os.rename(file, newPath)
    except Exception as e:
        print "Error: could not rename %s" % file
        print "Reason: %s" % str(e)
        print ""
        return
    
    time.sleep(0.05)
    
    try:
        os.rename(newPath, file)
    except Exception as e:
        print "WARNING!!! Successfully renamed file: %s" % file
        print "but could not change its name back again!"
        print "It is current named: %s" % os.path.basename(newPath)
        print "Reason: %s" % str(e)

def queryFixExcluded(excluded):
    if len(excluded) == 0:
        return
    
    while True:
        print ("\nAdd excluded files?\n"
               "NOTE: many files that are marked as excluded really are meant\n"
               "to be excluded. This tool is a rather blunt one and will only\n"
               "add all of the excluded files in one batch. If there are files\n"
               "listed here that you do want excluded, consider modifying the\n"
               "'userIgnore' variable in this script, or individually adding\n"
               "them yourself using 'tmutil removeexclusion path-to-file'.\n"
               "\n(Basically, if you don't know what this all means or are\n"
               "unsure what to do, you probably do NOT want to do this.)\n\n"
               "Proceed? [y/N]")
        response = raw_input()
    
        if response.lower() == 'y':
            for file in excluded:
                addToTimeMachineBackup(file)
            
            break
        elif response.lower() == 'n' or len(response) == 0:
            break

def queryFixIncluded(included):
    if len(included) == 0:
        return
    
    while True:
        print ("\nAttempt to fix non-excluded files not in backup by:\n"
               " 1. touching the files\n"
               " 2. touching their containing directories\n"
               " 3. changing their name and then changing it back again\n"
               "...in the hopes that it'll actually do something helpful? [Y/n]")
        response = raw_input()
    
        if response.lower() == 'y' or len(response) == '':
            for file in included:
                tryToFixMissingFile(file)
            
            break
        elif response.lower() == 'n':
            break

excludePaths = []
excludeUserPaths = []


def readStdExclusions():
    global excludePaths, excludeUserPaths
    
    def stripLeadingSlash(path):
        if path.startswith('/'):
            return path[1:]
        else:
            return path
    
    excl = plistlib.readPlist('/System/Library/CoreServices/backupd.bundle/Contents/Resources/StdExclusions.plist')
    excludePaths = [stripLeadingSlash(path) for path in excl['PathsExcluded'] + excl['ContentsExcluded'] + excl['FileContentsExcluded']]
    excludeUserPaths = [stripLeadingSlash(path) for path in excl['UserPathsExcluded']]

def initialize():
    readStdExclusions()

if __name__ == '__main__':
    if os.geteuid() != 0:
        print "This script must be run as root"
        exit(1)
    
    if len(sys.argv) > 2:
        print "Usage: python %s [path to directory]" % sys.argv[0]
        exit(1)
    
    initialize()
    
    try:
        if len(sys.argv) == 2:
            volume, path = pathToVolumeAndRelativePath(sys.argv[1])
            missing = findMissingFilesInFolder(volume, path)
        else:
            missing = findAndPrintMissingFilesInAllVolumes()
    
        excluded, included = determinedExcluded(missing)
        printResults(excluded, included)
        queryFixExcluded(excluded)
        queryFixIncluded(included)
        
    except myError as e:
        print e.message
        exit(1)
    
