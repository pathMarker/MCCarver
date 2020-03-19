# MCCarver
A tool to carve deleted minecraft files that are still present on your disk.

It also clasifies the results as well as it can using some post processing and tricks, but it has a lot of limitations.
Nonetheless, it allows you to take a look into the past using third party tools such as nbt explorer for general game data and mc edit for 3D region files. It was designed to retrieve release 1.8 files, but it's very flexible and should work to a good extent with any version.

This tool currently supports the recovery of the following file formats:
* Compressed minecraft logs (date.log.gz)
* Plain text logs (date.log)
* Level data files (level.dat)
* Player data (uuid.dat)
* Map data (map.dat)
* Region files (r.x.z.mca)
* Screenshots (it's very experimental and creates a lot of false positives, works only for 1.12.2 and above)

To use it just download python on your pc, place the files on a usb or other type of storage and execute MinecraftCarver.py. **Remember to run the program from a different drive**, or the results could overwrite what's already deleted on your disk, which could be awkward.
