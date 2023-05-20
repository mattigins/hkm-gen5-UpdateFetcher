import http.client
import os
import aiohttp
import asyncio
import configparser
import uuid
import glob
from urllib.parse import urlparse

validRegions = ["Eu","Au","Ru","Kr","Us","Ca","Nz","Me","Br","In","Tr"]
validModelNames = []
validModelINFs = []
INFDownloadURL = ""
possibleVersions = []

def selectRegion():
    for i, x in enumerate(validRegions):
        print("[" + str(i) + "] " + x)
    region = input("\nPlease enter your region number: ")
    try:
        token = getToken(validRegions[int(region)])
    except:
        clearScreen()
        print("[*] ERROR, Try Again\n")
        selectRegion()

def getToken(region):
    global possibleVersions

    clearScreen()

    years = list(range(18, 28))
    months = list(range(1, 13))
    revs = list(map(chr, range(ord('a'), ord('z')+1)))

    if region == 'Kr':
        possibleVersions = [f"20{year}{month:02}{rev}" for year in years for month in months for rev in revs]
    else:
        possibleVersions = [f"{year}{month:02}{rev}" for year in years for month in months for rev in revs]

    print("[*] Getting \"" + region + "\" Token..")

    conn = http.client.HTTPSConnection("apieu.map-care.com")

    payload = "{\"D1\": \"" + region + "\"}"

    headers = {
        'content-type': "application/json",
        'cache-control': "no-cache"
        }

    conn.request("POST", "/api/GetGUIDV2", payload, headers)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    
    token = data.decode("utf-8").split("|")[1].strip()

    print("[*] Getting HM Models")
    getModels(region, "HM", token)

    print("[*] Getting KM Models")
    getModels(region, "KM", token)

    print("[*] Getting GN Models")
    getModels(region, "GN", token)

    clearScreen()
    for i, x in enumerate(validModelNames):
        print("[" + str(i) + "] " + x)

    selectedINF = input("\nPlease enter your model number: ")
    bruteForceRevs(validModelINFs[int(selectedINF)])

def getModels(region, type, token):
    global INFDownloadURL
    conn = http.client.HTTPSConnection("apieu.map-care.com")

    payload = "{\"D1\": \"\",\"D2\": \"" + type + "\",\"D3\": \"\",\"D4\": \"" + region + "\",\"D5\": \"" + token + "\",\"D6\": \"U\"}"

    headers = {
        'content-type': "application/json",
        'cache-control': "no-cache"
        }

    conn.request("POST", "/api/ChkRegistV2", payload, headers)

    res = conn.getresponse()
    data = res.read()

    conn.close()

    dataLines = data.decode("utf-8").split("\n")
    url = dataLines[3].replace('#!#','').strip()
    INFDownloadURL = url.rsplit('/', 1)[0] + '/'


    for x in dataLines[4].split("|"):
        if len(x) > 1 and not x.isnumeric() and not "$" in x:
            validModelNames.append(x)

    for x in dataLines[0].split("|"):
        if ".inf$1" in x:
            model = x.rstrip("$1")
            validModelINFs.append(model.strip())

def bruteForceRevs(inf):
    clearScreen()
    print("[*] Searching For All Revisions (This will take a while)")
    urls = []

    for i, x in enumerate(possibleVersions):
        urls.append(INFDownloadURL + x + '/' + inf)

    asyncio.run(testURLs(urls))


async def get_async(url):
    async with aiohttp.ClientSession() as session:
        return await session.get(url)


async def testURLs(urls):
    validURLs = []
    resps = await asyncio.gather(*map(get_async, urls))

    for data in resps:
        if data.status == 200:
            validURLs.append(str(data.url))

    selectRevision(validURLs)

def selectRevision(validURLs):
    clearScreen()
    if len(validURLs) > 0:
        for i, url in enumerate(validURLs):
            print('[' + str(i) + '] ' + url.rsplit('/', 2)[1])

        selectedRev = input("\nPlease enter the revision number: ")
        parseINF(validURLs[int(selectedRev)])
    else:
        print("[*] No Valid Firmware Found :(")

def parseINF(url):
    url = urlparse(url)

    conn = http.client.HTTPConnection(url.netloc)
    conn.request("GET", url.path)
    res = conn.getresponse()
    data = res.read()
    conn.close()

    inf = []
    data = data.decode("utf-8", "ignore").split("\n")
    for x in data:
        inf.append(x.replace("[FILE_", "["+ str(uuid.uuid4()) +"_FILE_"))
    data = '\n'.join(inf)
    del inf

    config = configparser.ConfigParser()
    config.read_string(data)

    downloadSize = convertSize(int(config["ENVIRONMENT"]["FILE_FOLDER_SIZE"]))
    carName = removeQuotes(config["ENVIRONMENT"]["CAR_NAME"]).replace("-", "_").replace(" ", "_")
    rootUrl = removeQuotes(config["ENVIRONMENT"]["ROOT_URL"])
    modelPrefix = removeQuotes(config["ENVIRONMENT"]["MODEL_PREFIX"])
    destDirModel = "Downloads/" + carName + "/" + rootUrl.rsplit('/',1)[1] + "/" + modelPrefix

    print("Download Size:" + downloadSize + "\n")

    for section in config.sections():
        if "_FILE_" in section:
            zipSize = removeQuotes(config[section]["AG_ZIPSIZE"])
            fileSize = removeQuotes(config[section]["AG_FILESIZE"])
            fileName = removeQuotes(config[section]["AG_FILENAME"])
            zipName = removeQuotes(config[section]["AG_ZIPNAME"])
            fileInfoPath = removeQuotes(config[section]["FILEINFO_PATH"]).replace("$MODEL_PREFIX$", modelPrefix)
            numSpan = removeQuotes(config[section]["AG_NUMSPAN"])
            urls = []
            if int(numSpan) > 1:
                zipNum = range(1, int(numSpan) + 1)

                for x in zipNum:
                    fileExt = zipName.replace(".ZIP", ".z"+ str(x).zfill(2))
                    if str(x) == str(numSpan):
                        fileExt = zipName

                    urls.append([rootUrl + "/" + fileInfoPath + "/" + zipName.replace(".ZIP", str(x).zfill(3) + ".ZIP"), destDirModel + "/" + fileInfoPath + "/" + fileExt, zipSize])
            else:
                urls.append([rootUrl + "/" + fileInfoPath + "/" + fileName, destDirModel + "/" + fileInfoPath + "/" + fileName, fileSize])
            

            for url in urls:
                dest = url[1].replace("\\","/")
                fileStr = dest.rsplit('/',1)[1]
                size = url[2]
                url = urlparse(url[0].replace("\\","/").replace(" ", "%20"))
                conn = http.client.HTTPConnection(url.netloc)
                conn.request("GET", url.path)
                res = conn.getresponse()
                if res.status == 404:
                    print('[FILE NOT FOUND]')
                else:
                    bytes = res.read()

                    print("Downloading: " + fileStr + " (" + convertSize(size) + ")")
                    os.makedirs(dest.rsplit("/", 1)[0], exist_ok = True)
                    with open(dest, "wb") as f:
                        f.write(bytes)

                    if ".ZIP" in fileStr in fileStr:
                        prefix = dest.rsplit(".ZIP", 1)[0]
                        parts = glob.glob(prefix + "*")
                        os.system('ext "' + dest + '"')
                        for f in parts:
                            os.remove(f)

                conn.close()

    print("[*] ALL DONE! [*]")

def removeQuotes(str):
    return str.replace("\"", "")

def convertSize(size):
    return str(round(int(size) / 1000000, 2)) + "MB"

def clearScreen():
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')

selectRegion()