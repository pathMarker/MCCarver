import math, zlib
import ioManager, nbtUtils
from dataclasses import dataclass

@dataclass
class regFile:
    name: ""
    offset: int # offset in virtual sector
    sectors: int # size = sectors * chunkLen
    chunks: []
    x: int
    z: int
    errors: []
    realOffset: int # offset in disk
    datVer: bool

@dataclass
class chunk:
    offset: int
    sectors: int # size = sectors * chunkLen
    xPos: int
    zPos: int

@dataclass
class error:
    offset: int
    reason: ""

regData = None
coincidences = 0
chunkLen = 4096

prevOffset = 0
prevSectorSize = 0

def writeRegFile(regFile, compare, contenido):
    locations = bytearray([0]*chunkLen)
    timestamps = bytearray([0]*chunkLen)
    maxChunksPerCoord = 32
    entryLen = 4
    if len(regFile.chunks) > 0:
        regFileLen = regFile.sectors*chunkLen

        ioManager.outLog(regData.name + " from " + hex(regData.offset) + " to " + hex(prevOffset) + "; total chunks: " + str(len(regData.chunks)) + "; " + str(compare) + " sectors until next chunk;" + " |" + str(len(regData.errors)) + " errors")

        for err in regFile.errors:
            ioManager.outLog(regFile.name + " " + hex(err.offset) + " " + err.reason)
        
        for chunk in regFile.chunks:
            chunkSector = int((chunk.offset / chunkLen) + 2)
            x = chunk.xPos - (regFile.x*32)
            z = chunk.zPos - (regFile.z*32)

            entryZ = (maxChunksPerCoord * entryLen) * z
            entryX = entryLen * x
            entryOffset = entryZ + entryX

            locations[entryOffset:entryOffset+entryLen] = chunkSector.to_bytes(3, 'big') + chunk.sectors.to_bytes(1, "big")
        
        subfolder = "region18/"

        if regFile.datVer:
            subfolder = "region19/"
        
        ioManager.WriteFile(subfolder + regFile.name + "/" + hex(regFile.realOffset - 5) + "." + str(len(regFile.chunks))+"/"+regFile.name+".mca", locations + timestamps + contenido[regFile.offset:regFile.offset + regFileLen])

def nuevoArchivoReg(compare, contenido):
    global regData
    global coincidences

    sectors = int((prevOffset - regData.offset) / chunkLen) + prevSectorSize
    regData.sectors = sectors
    realErrors = []

    for err in regData.errors:
        if err.offset < regData.offset + regData.sectors * chunkLen:
            realErrors.append(err)
    
    regData.errors = realErrors

    writeRegFile(regData, compare, contenido)

    del regData
    coincidences = 0

def filterRegionFiles(offsetReal, header, contenido):
    global regData
    global coincidences
    global prevOffset
    global prevSectorSize

    wroteFile = False
    realChunkOffset = offsetReal - 5
    chunkOffset = header.start() - 5
    chunkSize = int.from_bytes(contenido[chunkOffset:chunkOffset+4], "big")
    extra = bytes()

    if chunkOffset < prevOffset + prevSectorSize * chunkLen:
        return # part of an already existing chunk

    if chunkSize >= 1048576:    # too large
        return #not a chunk
        
    if header.start() + chunkSize > len(contenido): # if the chunk gets trimmed by the program
        leng = (header.start() + chunkSize) - len(contenido)
        extra = ioManager.ReadSoft(leng, True)

    sectorSize = math.ceil((chunkSize+5)/chunkLen)
    
    chunkData = contenido[header.start(): header.start() + chunkSize] + extra
    try:
        data = zlib.decompress(chunkData)
    except:
        if regData:
            regData.errors.append(error(chunkOffset, "Decompress"))

        return
    
    if not nbtUtils.string2NBT("Entities", 0x9) in data:    # file doesn't follow chunk format
        if regData:
            regData.errors.append(error(chunkOffset, "Formato erroneo"))
        return #not a chunk

    compare = int((chunkOffset - prevOffset) / chunkLen)
    xPos = int.from_bytes(nbtUtils.getNBTval("xPos", data, 0x3), "big", signed=True)
    zPos = int.from_bytes(nbtUtils.getNBTval("zPos", data, 0x3), "big", signed=True)
    regionX = xPos >> 5
    regionZ = zPos >> 5

    if regData:
        if regionX != regData.x or regionZ != regData.z: # if the region file is different in this chunk than the previous one
            coincidences = 0
        elif compare > 255: # sector size cannot be higher than a byte
            coincidences = 0
            regData.errors.append(error(prevOffset, "Following sector size too high"))

    if coincidences > 0:
        regData.chunks[-1].sectors = compare
    else:
        if regData:
            wroteFile = True
            nuevoArchivoReg(compare, contenido)

        regionFileName = "r." + str(regionX) + "." + str(regionZ)
        regData = regFile(regionFileName, chunkOffset, 0, [], regionX, regionZ, [], offsetReal, False)

        if b"DataVersion" in data:
            regData.datVer = True
    
    coincidences += 1
    regData.chunks.append(chunk(chunkOffset - regData.offset, sectorSize, xPos, zPos))

    prevOffset = chunkOffset
    prevSectorSize = sectorSize

    return wroteFile

def flush(contenido):
    global regData
    global prevOffset
    global prevSectorSize

    if regData and len(regData.chunks) > 0:
        nuevoArchivoReg(0, contenido)
        regData = None

    prevOffset = 0
    prevSectorSize = 0

def filterMinecraftFiles(offsetReal, fileSize, analizar):
    wroteFile = False
    unCorruptedChunk = fileSize
    decompSize = 0
    chunk = bytes()
    i = 0

    while True:
        chunk = analizar[:decompSize + unCorruptedChunk]
        try:
            tryDecomp = zlib.decompressobj(wbits=zlib.MAX_WBITS | 16).decompress(chunk)
            decomp = tryDecomp
            decompSize += unCorruptedChunk

            if decompSize/fileSize >= 1:
                break
        except zlib.error as e:
            unCorruptedChunk = int(unCorruptedChunk/2)
            if unCorruptedChunk < 10:
                if decompSize == 0:
                    return # the file is not compressed
                break
    
    if b"Client thread" in decomp:
        ioManager.outLog("Client log file: " + hex(offsetReal))
        wroteFile = True
        ioManager.WriteFile("logs/client/" + hex(offsetReal) + ".log.gz", analizar)

    elif b"Server thread" in decomp:
        ioManager.outLog("Server log file: " + hex(offsetReal))
        wroteFile = True
        ioManager.WriteFile("logs/server/" + hex(offsetReal) + ".log.gz", analizar)

    elif nbtUtils.string2NBT("LevelName", 0x8) in decomp: # level.dat
        rootDir = "levelDat/"
        subDir = "Singleplayer/"
        ext = ".dat"

        levelName = nbtUtils.getNBTval("LevelName", decomp, 0x8).decode("utf-8")

        if nbtUtils.string2NBT("Time", 0x4) in decomp:
            if b"Player" in decomp:
                pass #Singleplayer
            elif int.from_bytes(nbtUtils.getNBTval("Time", decomp, 0x4), "big") == 0: # level.dat_mcr
                subDir = "Dat_mcr/"
                ext = ".dat_mcr"
            else:
                subDir = "Servers/"
        else:
            subDir = "Corrupt/"
        
        
        ioManager.outLog("level" + ext + ": " + hex(offsetReal))
        wroteFile = True
        ioManager.WriteFile(rootDir + subDir + levelName + "/" + hex(offsetReal) + "_level" + ext, analizar)

    elif nbtUtils.string2NBT("UUIDMost", 0x4) in decomp and nbtUtils.string2NBT("UUIDLeast", 0x4) in decomp: # playerdata
        rootDir = "playerdata/"

        uuid = nbtUtils.getNBTval("UUIDMost", decomp, 0x4).hex()
        
        ioManager.outLog("Playerdata file: " + hex(offsetReal))
        wroteFile = True
        ioManager.WriteFile(rootDir + uuid + "/" + hex(offsetReal) + ".dat", analizar)

    elif nbtUtils.string2NBT("scale", 0x1) in decomp: # map
        ioManager.outLog("Map data file: " + hex(offsetReal))
        rootDir = "maps"
        wroteFile = True
        ioManager.WriteFile(rootDir + "/" + hex(offsetReal) + ".dat", analizar)
    
    return wroteFile