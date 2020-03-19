x = 1
def string2NBT(tagName, tipo):
    name = tagName.encode()
    length = len(name).to_bytes(2, "big")
    return bytes([tipo]) + length + name

def getNBTval(tagName, data, tagType):
    tagNameSize = len(tagName)
    nameIndex = data.rfind(string2NBT(tagName, tagType)) + 3

    if nameIndex == 2:
        raise Exception("NBT Tag " + tagName + " no encontrada")
    num = 0
    tagDatLen = -1
    offset = 0
    if tagType == 0x8: # String
        tagDatLen = int.from_bytes(data[nameIndex + tagNameSize :nameIndex + tagNameSize + 2], "big")
        offset = 2
    elif tagType == 0x1: # Byte
        tagDatLen = 1
    elif tagType == 0x2: # Short
        tagDatLen = 2
    elif tagType == 0x3: # Int
        tagDatLen = 4
    elif tagType == 0x4: # Long
        tagDatLen = 8

    if tagDatLen == -1:
        raise Exception("TAG TYPE ERROR: type " + str(tagType))

    ultimoByte = nameIndex + tagNameSize + offset + tagDatLen
    tagValue = data[nameIndex + tagNameSize + offset: ultimoByte]
    return tagValue