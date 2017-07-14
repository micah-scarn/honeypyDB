from pymongo import MongoClient

class DatabaseController(object):
    def __init__(self, dbName, collection, ip = "localhost:27017"):
        self.client = MongoClient("mongodb://" + ip)
        self.dbName = self.client[dbName]
        self.collection = collection

    def add(self, data):
        if isinstance(data, list):
            return self.dbName[self.collection].insert_many(data)
        else:
            return self.dbName[self.collection].insert(data)

    def edit(self, data, filters = {}):
        response = None
        if isinstance(data, list):
            response = self.dbName[self.collection].update_many(filters, data)
        else:
            response = self.dbName[self.collection].update(filters, data)
        return response

    def patch(self, data, filters = {}):
        data = self.dbName[self.collection].update(filters, {"$set":data})
        return data

    def extendArray(self, data, filters = {}):
        data = self.dbName[self.collection].find_and_modify(filters, {"$push":data})
        return data

    def getData(self, data = {}, multiple = True):
        if multiple:
            return self.dbName[self.collection].find(data)
        else:
            return self.dbName[self.collection].find_one(data)

    def delete(self, data = None):
        return self.dbName[self.collection].delete_one(data)
