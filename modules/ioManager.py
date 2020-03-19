import os, math, psutil
from dataclasses import dataclass

folder = "d/"
root = ""
genEOF = bytes([0]*(0xF*2)) # 2*16 zero bytes
logFile = None

def WriteFile(name, data):
    path = folder + root + name

    if not os.path.exists(os.path.dirname(path)):
        try:
            os.makedirs(os.path.dirname(path))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    
    with open(path, "wb") as f:
        f.write(data)
        f.close()

def ReadSoft(length, goBack=False): # ensures the disk doesn't get overloaded in low-end systems by reading in small packets
    packetLen = 5000
    initOff = disk.data.tell()
    res = bytes()
    
    for i in range(math.ceil(length/packetLen)):
        if length < packetLen:
            res += disk.data.read(length)
        else:
            res += disk.data.read(packetLen)
            length -= packetLen
    
    if goBack:
        disk.data.seek(math.floor(initOff/1024)*1024)
        disk.data.read(initOff-math.floor(initOff/1024)*1024)
    
    return res

def getRealOffset(sectorOffset):
    return (disk.currSlice-1)*disk.sliceLen + sectorOffset

def outLog(line):
    logFile.write(line + "\n")
    print(line)

def findFileSize(contenido, header, sizeLimit = math.pow(10,6) * 10, footer = genEOF):    # brute forces the length of any file by finding a long string of zeros at its end
    extraContent = bytes()
    offset = 0
    setFooter = set(footer)
    
    fileSize = -1
    attempts = 0
    testSize = 60000 # 60kb
    testIncrement = 1024 * 8 # 8 kib

    while fileSize == -1:
        newLen = testSize + testIncrement * attempts

        if header.start() + newLen >= len(contenido):        # this header starts a file that has been trimmed by the sector division, we have to keep reading it
            newContent = ReadSoft((header.start() + newLen) - len(contenido))
            extraContent += newContent

            if not newContent: # if the disk file has ended
                contenido += extraContent
                return newLen - testIncrement
            else:
                if header.start() + offset < len(contenido):
                    chunk = contenido[header.start() + offset:] + extraContent
                    
                else:
                    chunk = extraContent[(header.start() + offset) - len(contenido):]

        else:
            chunk = contenido[header.start() + offset:header.start() + newLen]
        
        untilEOF = chunk.find(footer)
        
        if untilEOF != -1:
            fileSize = offset + untilEOF
        
        if not chunk[len(chunk)-1] in setFooter: # ensures we don't trim any footers
            offset = newLen
        
        if newLen > sizeLimit: # 10 Mb, too large
            fileSize = newLen
        
        attempts += 1

    if extraContent:
        contenido += extraContent

    return fileSize

# disk
startSlice = 1
disk = None

@dataclass
class imageFile:
    name: ""
    data: object
    sliceLen: int
    size: int
    slices: int
    currSlice: int

def readSlice():
    disk.data.seek((disk.currSlice-1)*disk.sliceLen)
    readExtra = len(genEOF)             # genEOF is the largest header we need to keep track of
    contenido = disk.data.read(disk.sliceLen + readExtra) # read some extra data to prevent header trimming (if a file with an intact header we want is trimmed we just read more data on the fly)
        
    return contenido

def getImageSize(fo):
    if fo.name.startswith("\\\\.\\"):   # a windows disk
        total, used, free = shutil.disk_usage(fo.name[4:])
        return total
    else:
        offset = fo.tell()
        fo.seek(0, os.SEEK_END)
        size = fo.tell()
        fo.seek(offset)
        
        return size
    #return 481790259200

def prepareFile(path, sliceLen):
    global disk
    global folder
    global logFile

    name = path[path.rfind('/')+1:]
    name = name[name.rfind('\\')+1:]
    name = name.replace(":", "")
    folder = name + "/"

    try:
        os.makedirs(folder)
        logFile = open(folder + "analisis.log", "a")
    except FileExistsError as fe: # Guard against race condition
        print("There are already results for this file, rename them or delete them to proceed")
        quit()
    
    data = open(path, "rb")
    data.seek((startSlice-1)*sliceLen, 0)

    totalSlices = int(math.ceil(getImageSize(data) / sliceLen))

    disk = imageFile(name, data, sliceLen, getImageSize(data), totalSlices, startSlice)
    outLog("Saving in " + folder + ", total disk slices to analyze: " + str(totalSlices) + ", total disk size: " + str(disk.size*10**-9) + " GB")
    outLog("Starting with slice " + str(startSlice) + " (change it in ioManager.py if desired)")
