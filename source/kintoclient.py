import kinto_http
from pprint import pprint
from PyQt5.QtWidgets import (QAction, QApplication, QDialog, QFileDialog,
                             QMessageBox, QStyleFactory, QSystemTrayIcon, qApp)
import globalref

class kintoClient():

    def __init__(self):
        #pass
        self.auth=('igor','WCinJ21.05.')


    
        #self.message("Init")

    def message(self,errorMsg):

        #globalref.baseCPath = basePath
        #errorMsg = _('blah blah')
        #errorMsg=pprint(errorMsg)
        QMessageBox.warning(None, 'TreeLine',
                            _('{}').
                            format(errorMsg))

    def buttonClick(self):

        #self.test()

        #globalref.baseCPath = basePath

        struct = globalref.mainControl.activeControl.structure

        fileData = struct.fileData()
        #pprint(fileData['nodes'])
        #pprint(fileData['properties'])
        #pprint(fileData['formats'])
        
        self.test(fileData['nodes'])


        
        for node in struct.descendantGen():
            
            nodeFormat = node.formatRef
            
            element = nodeFormat.name
            #pprint(node.data['Name'] + ' ' + str(element))
            
            #element.tail = '\n'
            #for fieldName in nodeFormat.fieldNames():
            #    text = node.data.get(fieldName, '')
                
            #    pprint('    ' + text)


            
            #    if text and fieldName != imports.genericXmlTextFieldName:
            #        element.set(fieldName, text)
            #if imports.genericXmlTextFieldName in nodeFormat.fieldDict:
            #    text = node.data.get(imports.genericXmlTextFieldName, '')
            #    if text:
            #        element.text = text
            
        

        #topNodeIds = set([node.uId for node in struct.childList])
        
        #nodeData = [data for data in fileData['nodes'] if data['uid'] in
        #            topNodeIds]

        
        #pprint(globalref.mainControl.activeControl.structure.fileData) #['b16ccba9cf3e11eaafa7a92edd9af87c'])

        errorMsg = _('done')
        #errorMsg=pprint(errorMsg)
        #QMessageBox.warning(None, 'TreeLine',
        #                    _('{}').
        #                    format(errorMsg))
        

    def test(self, data):

        self.client = kinto_http.Client(server_url="http://localhost:1234/v1", auth=self.auth)
        #kinto_http.Client.update_record(

        #client.create_group(id="igor", if_not_exists=True)
        #buck=client.get_buckets()[0]['id']
        #client.create_collection(id="test", if_not_exists=True)

        #record = globalref.mainControl.activeControl.structure.fileData
        for record in data:
        

            #record={"id":"vorever1", "content":"Neki detalji","title":"Naslov 05"}
            #self.client.create_record(id=record['uid'], collection="test",  data=record, if_not_exists=True)
            self.client.patch_record(id=record['uid'], collection="test",  data=record, if_match=False)


    def json_schema(self):
        node = {
              "type": "object",
              "properties": {
                "uid": {
                  "type": "string",
                  "name": "UID",
                  "description": "Node UID"
                },
                "format": {
                  "type": "string",
                  "name": "Format",
                  "description": "Format Type"
                },
                "children": {
                  "type": "array",
                  "name": "Children",
                  "description": "All the children",
                  "items": {
                    "type": "string"
                  }
                },
                "data": {
                  "type": "object",
                  "name": "Data",
                  "description": "All data",
                  "properties": {
                    "Name": {
                      "type": "string",
                      "name": "Entry Name",
                      "description": "Entry Name"
                    },
                    "Text": {
                      "type": "string",
                      "name": "Text",
                      "description": "Text"
                    }
                  }
                }
              }
            }

