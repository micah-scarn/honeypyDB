import re
from pymongo import MongoClient
from bson.objectid import ObjectId

class Tree(object):
    def __init__(self, db, collection, phrase = False, ip = "localhost:27017"):
        self.client = MongoClient("mongodb://" + ip)
        self.dbName = self.client[db]
        self.collection = collection
        self.phrase = phrase

    def response(self, **kwargs):
        if "status" not in kwargs:
            return
        if "data" not in kwargs:
            kwargs["data"] = None
        if "result" not in kwargs:
            if "errors" in kwargs:
                kwargs["result"] = "failure"
            else:
                kwargs["result"] = "success"
        if "errors" not in kwargs:
            kwargs["errors"] = None
        return {
            "result":kwargs["result"],
            "status":kwargs["status"],
            "data":kwargs["data"],
            "errors":kwargs["errors"]
        }

    def create(self, data):
        result = self.ifValidPath(data)
        if result:
            return result
        return self.createNode(data["path"])

    def get(self, path):
        data = {"path":path}
        result = self.ifValidPath(data)
        if type(result) == list:
            return result
        node = self.getNode(path)
        if node:
            return self.response(status = 200, data = node)
        else:
            return self.response(status = 404, errors = "Unable to find path")

    def getPhraseById(self, phraseId):
        node = self.dbName[self.collection].find({"properties.id":phraseId})
        if not node:
            return self.response(status = 404, errors = "Unable to find phrase by ID")
        node = self.cleanObjectId(node)
        node = self.cleanseCursorObject(node)
        if node:
            return self.response(status = 200, data = node)
        else:
            return self.response(status = 404, errors = "Uanble to find phrase by ID")

    def save(self, data):
        result = self.ifValidPath(data)
        if type(result) == list:
            return result
        node = self.getNode(data["path"])
        if node:
            return self.saveNode(data)
        else:
            return self.response(status = 404, errors = "Unable to find path")

    def saveNode(self, data):
        if self.phrase:
            return self.savePhrase(data)
        elif not self.phrase:
            return self.saveTest(data)

    def saveTest(self, data):
        for key in data:
            if re.match(r"browser", key, re.I):
                self.dbName[self.collection].update({"path":data["path"]}, {"$set": {"properties.browser":data[key]}})
            elif re.match(r"host", key, re.I):
                self.dbName[self.collection].update({"path":data["path"]}, {"$set": {"properties.host":data[key]}})
            elif re.match(r"url", key, re.I):
                self.dbName[self.collection].update({"path":data["path"]}, {"$set": {"properties.url":data[key]}})
            elif re.match(r"content", key, re.I):
                self.dbName[self.collection].update({"path":data["path"]}, {"$set": {"properties.content":data[key]}})
        node = self.getNode(data["path"])
        return self.response(status = 200, data = node)

    def savePhrase(self, data):
        for key in data:
            if re.match(r"id", key, re.I):
                self.dbName[self.collection].update({"path":data["path"]}, {"$set": {"properties.id":data[key]}})
            elif re.match(r"content", key, re.I):
                self.dbName[self.collection].update({"path":data["path"]}, {"$set": {"properties.content":data[key]}})
        node = self.getNode(data["path"])
        return self.response(status = 200, data = node)

    def createNode(self, path):
        path = self.checkValidPath(path)
        results = self.getNode(path)
        if not results:
            self.getDirectoryList(path)
            self.checkPath()
            if self.ifValidFile(path):
                self.createFileNode(path)
            else:
                self.createFolderNode(path)
            return self.response(status = 201, data = path)
        else:
            return self.response(status = 409, errors = "Path already exists")

    def checkValidPath(self, path):
        if not self.ifValidFile(path):
            if "/" != path[-1]:
                path += "/"
            if path[0] != "/":
                path = "/" + path
        return path

    def delete(self, path):
        data = {"path":path}
        result = self.ifValidPath(data)
        if result:
            return result
        if path == "/":
            return self.response(status = 409, errors = "Unable to delete root directory")
        return self.deleteNodes(data["path"])

    def deleteNodes(self, path):
        node = self.getNode(path)
        if not node:
            return self.response(status = 404, errors = "Unable to find path")
        else:
            self.removeParent(path)
            if not self.ifValidFile(path):
                self.deleteChildren(node)
            self.deleteNode(path)
            return self.response(status = 204)

    def removeParent(self, path):
        parentPath = self.getParentNode(path)
        self.removeChildNode(parentPath, path)

    def deleteChildren(self, node):
        for child in node["children"]:
            self.deleteNode(child)

    def createFolderNode(self, path):
        parent = self.getParentNode(path)
        self.checkParent(parent, path)
        folder =  {
            "type":"folder",
            "name":self.getNodeName(path),
            "path":path,
            "children":[],
            "parent":parent
        }
        self.addNode(folder)

    def createFileNode(self, path):
        parent = self.getParentNode(path)
        self.checkParent(parent, path)
        if self.phrase:
            node = self.createPhraseObject(path, parent)
        elif not self.phrase:
            node = self.createTestObject(path, parent)
        self.addNode(node)

    def createTestObject(self, path, parent):
        return {
            "type":"file",
            "name":self.getNodeName(path),
            "path":path,
            "parent":parent,
            "properties": {
                "url":"",
                "browser":"Chrome",
                "host": None,
                "content":"",
                "set":False
            }
        }

    def createPhraseObject(self, path, parent):
        return {
            "type":"file",
            "phrase":True,
            "name":self.getNodeName(path),
            "path":path,
            "parent":parent,
            "properties": {
                "id":"",
                "content":""
            }
        }

    def checkPath(self):
        if self.directoryList:
            for index in range(len(self.directoryList)):
                path = self.directoryList[index]
                if index < len(self.directoryList) - 1:
                    node = self.getNode(path)
                    if not node:
                        if not self.ifValidFile(path):
                            self.createFolderNode(path)
                        else:
                            self.createFileNode(path)

    def getParentNode(self, path):
        matches = re.match(r"^(.+)\/([^\/]+)\/?$", path, re.I|re.M)
        if matches:
            return matches.group(1) + "/"
        else:
            return "/"

    def getNodeName(self, path):
        matches = re.match(r"^(.+)\/([^\/]+)\/?$", path, re.I|re.M)
        if matches:
            return matches.group(2)
        else:
            return path.replace("/", "")

    def getDirectoryList(self, path):
        self.directoryList = []
        split = path.split("/")
        path = "/"
        for item in split:
            if item:
                if not self.ifValidFile(item):
                    path += item + "/"
                else:
                    path += item
                self.directoryList.append(path)


    def checkParent(self, parent, child):
        node = self.getNode(parent)
        if node:
            try:
                index = node["children"].index(child)
            except ValueError:
                print("\n > VALUE ERROR CHECK PARENT")
                self.addChildNode(parent, child)

    def rename(self, data):
        if "destination" not in data or not data["destination"]:
            return self.response(status = 400, errors = "Please provide valid destination path")
        if "original" not in data or not data["original"]:
            return self.response(status = 400, errors = "Please provide valid original path")
        if re.search(r"(\/{2,})", data["destination"]):
            return self.response(status = 400, errors = "Invalid destination path")
        if re.search(r"(\/{2,})", data["original"]):
            return self.response(status = 400, errors = "Invalid original path")
        return self.renameNode(data)

    def renameNode(self, data):
        if not data["original"]:
            return self.response(status = 404, errors = "Unable to find file. File to be copied does not exist")
        if not self.ifFile(data["original"]) or not self.ifFile(data["destination"]):
            return [400, "Unable to rename folders"]
        original = self.getNode(data["original"])
        ifDestination = self.getNode(data["destination"])
        if ifDestination:
            return self.response(status = 409, errors = "Destination file already exists")
        if self.phrase:
            return self.renameFileNode(original, data["destination"], data["id"])
        else:
            return self.renameFileNode(original, data["destination"])

    def renameFileNode(self, original, destination, phraseId = None):
        if self.ifValidFile(original["path"]) and self.ifValidFile(destination):
            self.delete(original["path"])
            self.getDirectoryList(destination)
            self.checkPath()
            parent = self.getParentNode(destination)
            name = self.getNodeName(destination)
            original["name"] = name
            original["parent"] = parent
            original["path"] = destination
            original.pop("_id", None)
            if phraseId:
                original["properties"]["id"] = phraseId
            self.checkParent(parent, destination)
            self.addNode(original)
            return self.response(status = 201, data = self.getNode(destination))
        else:
            return self.response(status = 400, errors = "Invalid file/path")

    def copy(self, data):
        if "destination" not in data or not data["destination"]:
            return self.response(status = 400, errors = "Please provide valid destination path")
        if "original" not in data or not data["original"]:
            return self.response(status = 400, errors = "Please provide valid original path")
        if re.search(r"(\/{2,})", data["destination"]):
            return self.response(status = 400, errors = "Invalid destination path")
        if re.search(r"(\/{2,})", data["original"]):
            return self.response(status = 400, errors = "Invalid original path")
        return self.copyNode(data["original"], data["destination"])

    def copyNode(self, original, destination):
        if not self.ifFile(original) or not self.ifFile(destination):
            return self.response(status = 400, errors = "Unable to copy folders")
        original = self.getNode(original)
        ifDestination = self.getNode(destination)
        if not original:
            return self.response(status = 404, errors = "Unable to find file. File to be copied does not exist")
        if ifDestination:
            return self.response(status = 409, errors = "Destination file already exists")
        return self.copyFileNode(original, destination)

    def copyFileNode(self, original, destination):
        if self.ifValidFile(original["path"]) and self.ifValidFile(destination):
            self.getDirectoryList(destination)
            self.checkPath()
            parent = self.getParentNode(destination)
            name = self.getNodeName(destination)
            original["name"] = name
            original["parent"] = parent
            original["path"] = destination
            original.pop("_id", None)
            self.checkParent(parent, destination)
            self.addNode(original)
            return self.response(status = 201, data = self.getNode(destination))
        else:
            return self.response(status = 400, data = "Invalid file/path")


    def getRoot(self):
        root = self.dbName[self.collection].find_one({"path":"/"})
        if not root:
            self.createRoot()
            root = self.dbName[self.collection].find_one({"path":"/"})
        return self.cleanObjectId(root)

    def createRoot(self):
        root =  {
            "type":"folder",
            "name":None,
            "path":"/",
            "children":[],
            "parent":None,
            "properties":None
        }
        self.addNode(root)

    def getNode(self, path):
        results = self.dbName[self.collection].find({"path":path})
        node = self.cleanseCursorObject(results)
        return node

    def cleanseCursorObject(self, results):
        node = []
        for item in results:
            item = self.cleanObjectId(item)
            node.append(item)
        if len(node) == 1:
            node = node[0]
        return node

    def getDirectory(self):
        root = self.getRoot()
        nodes = self.getAllNodes()
        directory = self.createDirectory(root, nodes)
        return self.response(status = 200, data = directory)

    def getAllNodes(self):
        nodes = []
        items = self.dbName[self.collection].find({})
        for item in items:
            item = self.cleanObjectId(item)
            nodes.append(item)
        return nodes

    def editNode(self, path, node):
        if "_id" in node:
            node["_id"] = ObjectId(node["_id"])
        response = self.dbName[self.collection].update({"path":path}, node)
        if response["updatedExisting"] == False:
            # Verify successful document update
            raise ValueError

    def addNode(self, node):
        self.dbName[self.collection].insert(node)

    def addChildNode(self, parent, child):
        node = self.getNode(parent)
        try:
            if node["children"].index(child):
                pass
        except ValueError:
            response = self.dbName[self.collection].find_and_modify({"path":parent}, {"$push": {"children": child}})
            print(response)

    def removeChildNode(self, parent, child):
        response = self.dbName[self.collection].find_and_modify({"path":parent}, {"$pull": {"children": child}})
        print(response)

    def deleteNode(self, path):
        self.dbName[self.collection].delete_one({"path":path})

    def createDirectory(self, root, nodes):
        tree = {}
        for node in nodes:
            if node["parent"]:
                parent = node["parent"]
                if parent not in tree:
                    tree[parent] = []
                tree[parent].append(node)
        return self.loopChildNodes(root, tree)

    def loopChildNodes(self, node, tree):
        path = node["path"]
        try:
            node["children"] = tree[path]
            for index in range(len(node["children"])):
                if node["children"][index]["type"] == "folder":
                    node["children"][index] = self.loopChildNodes(node["children"][index], tree)
            return node
        except KeyError:
            return node

    def ifValidPath(self, data):
        if "path" not in data or not data["path"]:
            return self.response(status = 400, errors = "Path key not defined")
        if re.search(r"(\/{2,})", data["path"]):
            return self.response(status = 400, errors = "Invalid path provided")
        if self.ifFile(data["path"]):
            if not self.ifValidFile(data["path"]):
                return self.response(status = 400, errors = "Invalid file/path")

    def ifValidFile(self, path):
        if not self.phrase:
            return self.ifValidTest(path)
        else:
            return self.ifValidPhrase(path)

    def ifValidTest(self, path):
        matches = re.search(r"\.(ui|api|feature|test)$", path, re.I|re.M)
        if matches:
            return True
        else:
            return False

    def ifValidPhrase(self, path):
        matches = re.search(r"\.(phrase)$", path, re.I|re.M)
        if matches:
            return True
        else:
            return False

    def ifFile(self, path):
        if "." in path:
            return True
        else:
            return False

    def checkNodeType(self, node):
        if self.ifValidFile(node):
            return "file"
        else:
            return "folder"

    def cleanObjectId(self, node):
        if "_id" in node:
            node["_id"] = str(node["_id"])
        return node
