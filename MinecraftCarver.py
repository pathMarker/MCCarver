import re, sys, math
# importing modules
sys.path.append("modules/")
import mcFiles, nbtUtils, ioManager

print("Starting MC Carver!")
diskPath = input("Provide a disk/image file path (\\\\.\\X: on windows, /dev/sdXY on linux): ") 
recoverMC = True if input("Would you like to recover MC files? (Y/N):").upper() == "Y" else False
recoverLog = True if input("Would you like to recover log files? (Y/N):").upper() == "Y" else False
recoverExtra = True if input("Would you like to recover extra files? (chatsync) (Y/N):").upper() == "Y" else False
recoverPng = True if input("Would you like to recover screenshots? (False positives, can take up a lot of space) (Y/N):").upper() == "Y" else False

if recoverPng:
    dim = input("Provide your screen dimensions (e.g: 1920x1080)")
    if not dim:
        dim = "1920x1080"
    width, height = map(int, dim.split('x'))

sliceLen = int(math.pow(1024,3)/2)    # should be a multiple of the disk's sector size
ioManager.prepareFile(diskPath, sliceLen)
graphFile = open(ioManager.folder + "graph.plot", "a")

validFiles = 0
gzipHeader = b"\x1F\x8B\x08\x00\x00\x00\x00\x00\x00\x00"
zlibHeader = b"\x78\x9C"
chatsyncHeader = b"sCdB\x07"
logPattern = rb"\[\d\d:\d\d:\d\d\] \["
pngHeader = rb"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A\x00\x00\x00\x0D\x49\x48\x44\x52........\x08\x02\x00\x00\x00"    # all MC screenshots share this header, the x02 is present in 1.12.2 and older, newer versions like 1.13.2 use x06
pngFooter = b"\x49\x45\x4E\x44\xAE\x42\x60\x82"

def getChatSync(offsetReal, sliceData): # used for retrieving chatsync skype file
    size = int.from_bytes(sliceData[header.start()+9:header.start()+9+4], "little", signed=False) + 32

    content = sliceData[header.start():header.start()+size]
    ioManager.outLog("Chatsync file: " + hex(offsetReal))
    ioManager.WriteFile(hex(offsetReal) + ".dat", content)

def getPNG(offsetReal, data): # used for retrieving potential screenshots
    w = int.from_bytes(data[16:16+4], "big", signed=False)
    h = int.from_bytes(data[16+4:16+8], "big", signed=False)

    if (h >= height/6 and w >= width/6) and (h <= height and w <= width):   # we stablish some resolution limits we can work with
        ioManager.WriteFile(hex(offsetReal) + ".png", data)
    
def clearLastLine(analizar): # brute forces the last line of a minecraft plain text log file decoding until error
    try:
        analizar.decode("cp1252")
        logLine = analizar
    except UnicodeDecodeError as ex:
        logLine = analizar[0: ex.start]

    return logLine

for _ in range(ioManager.disk.slices): # loops all of the slices in disk
    sliceData = ioManager.readSlice()
    ioManager.outLog("Analyzing sector " + str(ioManager.disk.currSlice) + "/" + str(ioManager.disk.slices))

    # MC miscellaneous files (level data, player data, maps and compiled logs)
    if recoverMC:
        for header in re.finditer(gzipHeader, sliceData):

            if (header.start()) % 1024 != 0:
                ioManager.root = "MCFiles/Misaligned/"   # this folder contains misaligned files
            else:
                ioManager.root = "MCFiles/"

            offsetReal = ioManager.getRealOffset(header.start())

            fileSize = ioManager.findFileSize(sliceData, header)
            if fileSize == False:
                continue # too large
            
            analizar = sliceData[header.start():header.start()+fileSize]

            if mcFiles.filterMinecraftFiles(offsetReal, fileSize, analizar):
                validFiles += 1
        
        # region files (r.x.z.mca)
        ioManager.root = "RegionFiles/"
        for header in re.finditer(zlibHeader, sliceData):

            offsetReal = ioManager.getRealOffset(header.start())

            if mcFiles.filterRegionFiles(offsetReal, header, sliceData):
                validFiles += 1
        
        mcFiles.flush(sliceData) #TODO: they cut off at the end of the sector, create buffer!
    
    if recoverExtra:
        # simple chatsync implementation
        for header in re.finditer(chatsyncHeader, sliceData):
            ioManager.root = "chatsync/1/"

            offsetReal = ioManager.getRealOffset(header.start())

            getChatSync(offsetReal, sliceData)
    
    # recover potential screenshots
    if recoverPng:
        for header in re.finditer(pngHeader, sliceData):
            version = sliceData[header.start() + 25] # they 25th byte gives some insight on the version, see pngHeader comment
            offsetReal = ioManager.getRealOffset(header.start())
            idatOffset = header.end() + 8 # 8 is the added length of the CRC of the IHDR and the length of the IDAT chunk

            if len(sliceData) < idatOffset+4:
                sliceData += ioManager.ReadSoft((idatOffset+4)-len(sliceData))

            idatLen = int.from_bytes(sliceData[idatOffset-4:idatOffset], "big", signed=False) 

            if version == 0x2: # always true
                ioManager.root = "screenshots/1_12_2orOlder/"
            
                if idatLen <= 0x8000 and sliceData[idatOffset:idatOffset+4] == b"IDAT":
                    fileSize = ioManager.findFileSize(sliceData, header, math.pow(10,6) * 30, pngFooter)
                    nextIdat = idatOffset + idatLen + 8 + 4

                    # if the length of the first IDAT sector is less than the max size, 0x8000, the image is complete and doesn't have a second IDAT
                    if idatLen == 0x8000 or sliceData[nextIdat:nextIdat+4] != b"IDAT":
                        getPNG(offsetReal, sliceData[header.start():header.start()+fileSize])



    # recover plain text logs
    if recoverLog:
        ioManager.root = "PlainTextLogs/"
        newMClog = True
        firstLine = None
        prevLine = None
        maxEntryLen = 5000
        for logEntry in re.finditer(logPattern, sliceData):
            currLine = logEntry.start()
            if prevLine:
                distancia = currLine - prevLine
                if distancia > maxEntryLen:
                    newMClog = True
                    analizar = sliceData[prevLine: prevLine + maxEntryLen]
                    lastLine = clearLastLine(analizar)
            
            if newMClog:
                if firstLine:
                    ioManager.outLog("Plain text log: " + hex(ioManager.getRealOffset(firstLine)))
                    ioManager.WriteFile(hex(ioManager.getRealOffset(firstLine)) + ".log", sliceData[firstLine:prevLine] + lastLine)

                firstLine = currLine
                validFiles += 1
                newMClog = False
        
            prevLine = currLine

        if prevLine:
            analizar = sliceData[prevLine: prevLine + maxEntryLen]
            lastLine = clearLastLine(analizar)
            ioManager.outLog("Plain text log: " + hex(ioManager.getRealOffset(firstLine)))
            ioManager.WriteFile(hex(ioManager.getRealOffset(firstLine)) + ".log", sliceData[firstLine:prevLine] + lastLine)
    
    # write graph line to display later on
    graphFile.write(str(ioManager.disk.currSlice) + "\t" + str(validFiles) + "\n")

    if validFiles > 0:
        ioManager.outLog("End of slice " + str(ioManager.disk.currSlice) + ", " + str(validFiles) + " recovered in total\r\n")

    validFiles = 0
    ioManager.disk.currSlice += 1

ioManager.outLog("Success! You can review the results in the folder " + ioManager.folder)