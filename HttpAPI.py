#!/usr/bin/python3
# coding: utf-8
import os
import json
import re
import traceback
import urllib.parse
import time
from tarfile import is_tarfile

import docker

#~~~~~here is configures~~~~~~#
from docker.types import IPAMConfig, IPAMPool
from docker.utils import create_ipam_pool, create_ipam_config, utils

INTEND_INT = 4
TAR_UPLOADDIR = "/home/hanitek/DocumentRoot/tarpool/upload/"
TAR_DOWNLOADDIR = "/home/hanitek/DocumentRoot/tarpool/download/"


#http://code.activestate.com/recipes/410692-readable-switch-construction-without-lambdas-or-di/
# This class provides the functionality we want. You only need to look at
# this if you want to know how this works. It only needs to be defined
# once, no need to muck around with its internals.
class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration

    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False

current_milli_time = lambda: int(round(time.time() * 1000))

class httpResponse:
    #正常時
    def print200(self):
        print("HTTP/1.0 200 OK\n")

    #acttionなし
    def print400(self,msg,action = "null"):
        print("Status: 400 Bad Request\n")
        print(json.dumps({"error": True, "action": action, "return":[{"msg": msg}]}, indent=INTEND_INT))
        exit()

    #コンテナが見当たらないなど
    def print404(self,msg,action = "null"):
        print("Status: 404 Not Found\n")
        print(json.dumps({"error": True, "action": action, "return":[{"msg": msg}]}, indent=INTEND_INT))
        exit()

    #そのたパラメたの不足
    def print405(self,msg,action = "null"):
        print("Status: 405 Method Not Allowed\n")
        print(json.dumps({"error": True, "action": action, "return":[{"msg": msg}]}, indent=INTEND_INT))
        exit()

    #API接続エラー
    def print500(self,msg,action = "null"):
        print("Status: 500 Internal Server Error\n")
        print(json.dumps({"error": True, "action": action, "return":[{"msg": msg}]}, indent=INTEND_INT))
        exit()

httpResponse = httpResponse()

class httpRequest:
    def getQueries(self,rawquery):
        if rawquery is "":
            httpResponse.print400(msg="There are no queries.")
        return urllib.parse.parse_qs(rawquery)

    def checkVar(self, variablename, return400 = True):
        if variablename not in queries:
            if return400:
                httpResponse.print400("param "+variablename+" is not setted.")
            else:
                return None
        return  queries.get(variablename)[0]

httpRequest = httpRequest()

class DockerFuncs:
    def getAPI(self):
        try:
            c = docker.from_env()
            if not c.api.ping():
                httpResponse.print500("ErrorDockerAPI;ping error","ErrorDockerAPI")
            return c
        except Exception:
            httpResponse.print500("ErrorDockerAPI;"+str(traceback.format_exc()), "ErrorDockerAPI")

    def getContainerbyName(self, name):
        c = self.getAPI()
        # docker ps -aqf "name=busy1" get ID by name
        cont = None
        try:
            cont = c.containers.get(name)
        except Exception:
            resp = traceback.format_exc()
            if "Permission denied" in resp:
                httpResponse.print500(resp)
        return cont

    def issetCont(self, name):
        cont = DockerFuncs.getContainerbyName(name=name)
        if cont is None:
            httpResponse.print404("NotFoundContainer;"+str(name))
        return cont.id

    def getIpv40(self, contname):
        #docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' contname
        ins = self.inspectContainerbyID(contname)
        result = dict()
        result["success"] = ins["success"]
        #result["eth0"] = ins["result"]["NetworkSettings"]["IPAddress"]
        result["nets"] = dict()
        n = 0

        for key,value in ins["result"]["NetworkSettings"]["Networks"].items():
            result["nets"][key] = value["IPAddress"]

        for key,value in ins["result"]["NetworkSettings"]["Networks"].items():
            result["eth"+str(n)] = value["IPAddress"]
            n = n+1
        return result

    def plainFunctionForContainer(self, swichname, containerid, prvport=None):
        c = self.getAPI().api
        result = dict()
        try:
            for case in switch(swichname):
                if case("list"):
                    result["result"] = c.containers()
                    break
                if case("pause"):
                    result["result"] = c.pause(container=containerid)
                    break
                if case("unpause"):
                    result["result"] = c.unpause(container=containerid)
                    break
                if case("kill"):
                    result["result"] = c.kill(container=containerid)
                    break
                if case("restart"):
                    result["result"] = c.restart(container=containerid)
                    break
                if case("start"):
                    result["result"] = c.start(container=containerid)
                    break
                if case("stop"):
                    result["result"] = c.stop(container=containerid)
                    break
                if case("inspect"):
                    result["result"] = c.inspect_container(container=containerid)
                    break
                if case("remove"):
                    result["result"] = c.remove_container(container=containerid, link=False, force=True, v=True)
                    break
                if case("stats"):
                    result["result"] = str(c.stats(container=containerid, stream=True),'utf-8')
                    break
                if case("diff"):
                    result["result"] = c.diff(container=containerid)
                    break
                if case("top"):
                    result["result"] = c.top(container=containerid)
                    break
                if case("port"):
                    result["result"] = c.port(container=containerid, private_port=prvport)
                    break
                if case("logs"):
                    result["result"] = c.logs(container=containerid, stream=False)
                    break
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            return result
        result["success"] = True
        return result

    def listContainer(self):
        return self.plainFunctionForContainer("list", "AAAAAQAA")

    def inspectContainerbyID(self, id):
        return self.plainFunctionForContainer("inspect", id)

    def removeContainerbyID(self, id):
        return self.plainFunctionForContainer("remove", id)

    def pauseContainerbyID(self, containerid):
        return self.plainFunctionForContainer("pause", containerid)

    def unpauseContainerbyID(self, containerid):
        return self.plainFunctionForContainer("unpause", containerid)

    def killContainerbyID(self, id):
        return self.plainFunctionForContainer("kill", id)

    def restartContainerbyID(self, id):
        return self.plainFunctionForContainer("restart", id)

    def startContainerbyID(self, id):
        return self.plainFunctionForContainer("start", id)

    def stopContainerbyID(self, id):
        return self.plainFunctionForContainer("stop", id)

    def statsContainerbyID(self, id):
        return self.plainFunctionForContainer("stats", id)

    def diffContainerbyID(self, id):
        return self.plainFunctionForContainer("diff", id)

    def topContainerbyID(self, id):
        return self.plainFunctionForContainer("top", id)

    def portContainerbyID(self, id, prvport):
        return self.plainFunctionForContainer("port", id, prvport=prvport)

    def logsContainerbyID(self, id):
        return self.plainFunctionForContainer("logs", id)

    def commitContbyID(self, id, imgname, tagname, commitmessage=None, authorname=None, dockerfileline=None):
        c = self.getAPI().api
        result = dict()
        #conf = {"CMD":["apachectl", "-DFOREGROUND"],}
        #httpResponse.print405(dockerfileline)

        if self.isexistImage(imgname):
            httpResponse.print405("AlreadyExist;")

        try:
            if dockerfileline is None:
                result["result"] = c.commit(container=id, repository=imgname, tag=tagname, message=commitmessage,
                                            author=authorname)
            else:
                #"Volumes" "WorkingDir":"Entrypoint": null,
                if ( "Volumes" or "WorkingDir" or "Entrypoint") in dockerfileline:
                    httpResponse.print405("RequestInvalid;")
                result["result"] = c.commit(container=id,repository=imgname,tag=tagname,message=commitmessage,author=authorname,conf=dockerfileline)
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            return result
        result["success"] = True
        return result

    def execContbyID(self, id, cmd):
        c = self.getAPI().api
        result = dict()
        # cmd = ["echo", "hello"] cmd="echo hello"
        try:
            execstack = c.exec_create(container=id, cmd=cmd)
            result["result"] = urllib.parse.quote(c.exec_start(exec_id=execstack))
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            return result
        result["success"] = True
        return result

    def createContbyID(self): #TODO implement
        c = self.getAPI().api
        result = dict()
        # cmd = ["echo", "hello"] cmd="echo hello"
        try:
            c.create_container_config()
            c.create_container_from_config()
            c.create_container()
            c.create_container(en)
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            return result
        result["success"] = True
        return result

    def updateContbyID(self, cont, memory=None, cpu=None, restart=None):
        c = self.getAPI().api
        result = dict()
        try:
            restart_policy = None
            if "no" in restart:
                restart_policy={"Name": "no"}
            elif "always" in restart:
                restart_policy={"Name": "always"}
            elif "on-failure" in restart:
                restart_policy={"Name": "on-failure", "MaximumRetryCount": 5}
            elif "unless-stopped" in restart:
                restart_policy={"Name": "unless-stopped"}
            else:
                httpResponse.print405("RestartWrong;")
            if memory is not None:
                memory = str(memory) + "MB"

            url = c._url('/containers/{0}/update', cont)
            data = {}
            if restart_policy:
                data['RestartPolicy'] = restart_policy
            if cpu:
                data['NanoCpus'] = round(float(cpu)/float(0.000000001))
            if memory:
                data['Memory'] = utils.parse_bytes(memory)

            res = c._post_json(url=url, data=data)
            result["result"] =  c._result(res, True)
            #c.update_container(cont, mem_limit=memory, nano_cpus=cpu, restart_policy=restart_policy)
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            return result
        result["success"] = True
        return result

    def isexistImage(self, imgname):
        c = self.getAPI().api

        if imgname is None:
            return False
        try:
            jsonfry = c.search(imgname)
            for image in jsonfry:
                if str(imgname).lower() == str( image["name"] ).lower():
                    return True
        except Exception: pass
        try:
            c.inspect_image(imgname)
            return True
        except Exception:
            return False


    def plainFunctionForImage(self, swichname, imagename, version):
        c = self.getAPI().api

        if imagename is None or ":" in imagename or "//" in imagename or "&" in imagename or "!" in imagename:
            httpResponse.print405("NotAllowedChar;")

        result = dict()

        try:
            for case in switch(swichname):
                if case("pull"):
                    result["result"] = c.pull(repository=imagename, tag=version)
                    break
                if case("remove"):
                    result["result"] = c.remove_image(image=imagename +":"+ version)
                    break
                if case("inspect"):
                    result["result"] = c.inspect_image(image=imagename +":"+ version)
                    break
                if case("prune"):
                    result["result"] = c.prune_images({"dangling":True})
                    break
                if case("list"):
                    result["result"] = c.images()
                    break
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            return result
        result["success"] = True
        if "Downloaded" in result["result"]:
            result["result"] = "ImgDownloaded;Downloaded"
        if "Image is up to date" in result["result"]:
            result["result"] = "ImgDownloaded;Updated"
        return result

    def pullImage(self, imagename, version = "latest"):
        return self.plainFunctionForImage("pull", imagename, version)

    def deleteImage(self, imagename, version = "latest"):
        return self.plainFunctionForImage("remove", imagename, version)

    def inspectImage(self, imagename, version = "latest"):
        return self.plainFunctionForImage("inspect", imagename, version)

    def pruneImage(self):
        return self.plainFunctionForImage("prune", "AAAAAAAAA", "AAAAAA")

    def listImage(self):
        return self.plainFunctionForImage("list", "AAAAAAAAA", "AAAAAA")

    def importByURL(self, url, reponame, tagname):
        c = self.getAPI().api
        result = dict()

        imagename = reponame +":"+ tagname

        if imagename is None or "//" in imagename or "&" in imagename or "!" in imagename:
            httpResponse.print405("NotAllowedChar;")

        if self.isexistImage(reponame):
            httpResponse.print405("AlreadyExist;")

        try:
            result["result"] = c.import_image_from_url(url=url, repository=reponame, tag=tagname)
        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            if "no such host" in result["result"]:
                httpResponse.print404("NotFound;no such host", action="exportImgByURL")
            if "Not Found for url" in result["result"]:
                httpResponse.print404("NotFound;no such file", action="exportImgByURL")
            return result
        result["success"] = True
        if "invalid tar header" in result["result"]:
            httpResponse.print404("NotFound;url invalid", action="exportImgByURL")

        return result

    def importFrame(self, swichname, filename, imagename=None, tagname=None, targetpath=None, containername=None):
        c = self.getAPI().api
        result = dict()

        # filename assertion
        result["filename"] = re.sub(r'[^\w]', '', filename)
        result["url"] = ""
        result["result"] = ""

        if self.isexistImage(imagename):
            httpResponse.print405("AlreadyExist;")

        filepath = TAR_UPLOADDIR + result["filename"] + '.tar'

        try:
            if not os.path.exists(filepath):
                httpResponse.print404("NotFound;"+filepath, "importFrame")

            if not is_tarfile(filepath):
                httpResponse.print404("NotFound;"+filepath, "importFrame")

            for case in switch(swichname):
                if case("import"):
                    result["result"] = c.import_image_from_file(filename=filepath, repository=imagename,
                                             tag=tagname)
                    break
                if case("load"): #not working?
                    output = c.load_image(data=open(filepath,"rb").read())
                    linar = ""
                    for line in output:
                        linar = linar + str(line)
                    result["result"] = linar
                    break
                if case("extar"):
                    result["success"] = c.put_archive(container=self.issetCont(containername)
, path=targetpath,data=filepath)
                    break
            result["url"] = filepath

        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            if "ImageNotFound" in result["result"]:
                httpResponse.print404("NotFound;", action="exportImgByURL")
            return result
        result["success"] = True
        return result
    def importImgbyfilepath(self,filename, imagename, tagname):
        return self.importFrame("import", filename, imagename=imagename, tagname=tagname)
    # print(c.import_image_from_file(filename="./busybox-latestgetimage.tar",repository="title-busy",tag="latest"))

    def loadContainer(self, filename):
        return self.importFrame("load", filename)
    # print(c.load_image(data=tar))

    def extractTarBall(self, filename, containername, path):
        return self.importFrame("extar", filename, targetpath=path, containername=containername)
    # Insert a file or folder in an existing container using a tar archive assource.
    # c.put_archive("path",tardata)

    def exportFrame(self, swichname, filename, containername = None, targetdir=None, reponame=None, tagname=None):
        c = self.getAPI().api
        result = dict()

        # filename assertion
        result["filename"] = re.sub(r'[^\w]', ' ', filename)
        result["url"] = ""

        filepath = TAR_DOWNLOADDIR + result["filename"] + '.tar'

        try:
            bits = None

            # check container id
            for case in switch(swichname):
                if case("save"):
                    imagename = reponame + ":" + tagname
                    if imagename is None or "//" in imagename or "&" in imagename or "!" in imagename:
                        httpResponse.print405("NotAllowedChar;")
                    bits = c.get_image(imagename)
                    break
                if case("export"):
                    id = self.issetCont(containername)
                    bits = c.export(id)
                    break
                if case("mktar"):
                    id = self.issetCont(containername)
                    bits, stat = c.get_archive(container=id, path=targetdir)
                    result["result"] = stat
                    break

            f = open(filepath, 'wb')
            for chunk in bits:
                f.write(chunk)
            f.close()

            result["success"] = is_tarfile(filepath)
            result["url"] = filepath

        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()
            if "ImageNotFound" in result["result"]:
                httpResponse.print404("NotFoundImg;"+str(reponame), action="exportImgByURL")
            elif "Not Found for url" in result["result"]:
                httpResponse.print404("NotFound;", action="exportImgByURL")
            return result
        result["success"] = True
        return result

    def exportImgByURL(self, filename, reponame, tagname = "latest"):
        return self.exportFrame("save", filename, reponame=reponame, tagname=tagname)

    def getTarballbyContID(self, containername, dir, filename):
        return self.exportFrame("mktar", filename, targetdir=dir, containername=containername)

    def exportbyContID(self, containername, filename):
       return self.exportFrame("export",filename, containername=containername)

    def network(self, switchname, network=None, contname=None):
        c = self.getAPI().api
        result = dict()
        try:
            # check container id
            for case in switch(switchname):
                if case("prune"):
                    result["result"] = c.prune_networks()
                    break
                if network is None:
                    raise ValueError("value error!")
                if case("create"):
                    result["result"] = c.create_network(driver="overlay",internal=False, attachable=True, enable_ipv6=False, name=network, ipam=IPAMConfig(pool_configs=[IPAMPool(subnet="192.168.0.0/24")])
, scope="swarm")
                    break
                if case("remove"):
                    result["result"] = c.remove_network(net_id=network)
                    break
                if contname is None:
                    raise ValueError("value error!")
                if case("connect"):
                    result["result"] = c.connect_container_to_network(container=contname, net_id=network)
                    break
                if case("disconnect"):
                    result["result"] = c.disconnect_container_from_network(container=contname,net_id=network)
                    break
            result["success"] = True

        except Exception:
            result["success"] = False
            result["result"] = traceback.format_exc()

            if "No such network" in result["result"]:
                httpResponse.print404("network is not found", action="network")
            elif "Not Found for url" in result["result"]:
                httpResponse.print404("NotFound;", action="network")
            if "swarm is not active" in result["result"]:
                httpResponse.print500("SwarmDown;", action="network")
            return result
        result["success"] = True
        return result

DockerFuncs = DockerFuncs()

class eachPages:
    def default(self):
        httpResponse.print200()
        print(json.dumps({"error": False, "return": [{"msg": "this page is working."}], }, indent=INTEND_INT))

    def image(self, queries):
        action = httpRequest.checkVar("action")
        result = None

        if  "list" == action or "prune" == action:
            if "list" == action:
                result = DockerFuncs.listImage()

            if "prune" == action:
                result = DockerFuncs.pruneImage()
            if result["success"] is True:
                httpResponse.print200()
                print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
                exit()
            else:
               httpResponse.print500(result)

        imagename = httpRequest.checkVar("imgname")  # e.g. debian gotget/docker-novnc
        version = httpRequest.checkVar("tagname", return400=False)

        for case in switch(action):
            if case("pull"):
                result = DockerFuncs.pullImage(imagename=imagename, version=version)
                break
            if case("delete"):
                result = DockerFuncs.deleteImage(imagename=imagename, version=version)
                break
            if case("inspect"):
                result = DockerFuncs.inspectImage(imagename=imagename, version=version)
                break

        if result is None:
         httpResponse.print405("'action' is not correct! ", action)

        if result["success"] is True:
            result["imagename"] = imagename
            result["version"] = version

            httpResponse.print200()
            print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
            exit()
        elif "ImageNotFound" in result["result"]:
            httpResponse.print404("NotFound;Image", action=action)
        else:
            httpResponse.print404(result["result"], action=action)

    def container(self, queries):
        action = httpRequest.checkVar("action")

        if action == "list":
            result = DockerFuncs.listContainer()
            if result["success"] is True:
                httpResponse.print200()
                print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
                exit()
            else:
               httpResponse.print500(result)

        containername =  httpRequest.checkVar("containername")

        #check container id
        id = DockerFuncs.issetCont(containername)
        result = None
        for case in switch(action):

            #ex http://cgitest/test/httpAPI.py?page=container&action=getid&containername=busy1
            if case("getid"):
                httpResponse.print200()
                print(json.dumps({"error": False, "action": action, "return": [{"id":id }],  }, indent=INTEND_INT))
                exit()
                break
            if case("getip"):
                httpResponse.print200()
                print(json.dumps({"error": False, "action": action, "return": DockerFuncs.getIpv40(id),  }, indent=INTEND_INT))
                exit()
                break
            if case("commit"):  # It is good condition container is paused while commiting.
                if result is None:
                    imgname = httpRequest.checkVar("imgname")
                    tagname = httpRequest.checkVar("tagname", return400=False)
                    authorname = httpRequest.checkVar("authorname", return400=False)
                    commitmsg = httpRequest.checkVar("commitmsg", return400=False)
                    #e.g.         conf = {"CMD":["apachectl", "-DFOREGROUND"]}
                    # param dockerfileline=%7B%22CMD%22%3A%5B%22apachectl%22%2C%20%22-DFOREGROUND%22%5D%7D
                    dockerfileline = httpRequest.checkVar("dockerfileline", return400=False)
                    if dockerfileline is not None:
                        try:
                            dockerfileline = json.loads(dockerfileline)
                        except Exception:
                            httpResponse.print405("json strcture is not correct.")
                    if tagname is None:
                        tagname = "latest"
                    result = DockerFuncs.commitContbyID(id, imgname=imgname, tagname=tagname, authorname=authorname, commitmessage=commitmsg, dockerfileline = dockerfileline)
            if case("exec"):
                if result is None:
                    cmd = httpRequest.checkVar("cmd")
                    result = DockerFuncs.execContbyID(id, cmd)
            if case("inspect"):
                if result is None:
                    result = DockerFuncs.inspectContainerbyID(id)
            if case("remove"):
                if result is None:
                    result = DockerFuncs.removeContainerbyID(id)
            if case("pause"):
                if result is None:
                    result = DockerFuncs.pauseContainerbyID(id)
            if case("unpause"):
                if result is None:
                    result = DockerFuncs.unpauseContainerbyID(id)
            if case("kill"):
                if result is None:
                   result = DockerFuncs.killContainerbyID(id)
            if case("restart"):
                if result is None:
                    result = DockerFuncs.restartContainerbyID(id)
            if case("start"):
                if result is None:
                   result = DockerFuncs.startContainerbyID(id)
            if case("stop"):
                if result is None:
                    result = DockerFuncs.stopContainerbyID(id)
            if case("stats"):
                if result is None:
                    result = DockerFuncs.statsContainerbyID(id)
            if case("diff"):
                if result is None:
                    result = DockerFuncs.diffContainerbyID(id)
            if case("top"):
                if result is None:
                    result = DockerFuncs.topContainerbyID(id)
            if case("port"):
                if result is None:
                    prvport = httpRequest.checkVar("private_port")
                    result = DockerFuncs.portContainerbyID(id, prvport)
            if case("logs"): #This implement is no worth using
                if result is None:
                    result = DockerFuncs.logsContainerbyID(id)
            if case("create"):
                if result is None:
                    result = DockerFuncs.createContbyID(id)
            if case("update"):#別にstorage-optが増やせるわけではない
                if result is None:
                    memory = httpRequest.checkVar("memory",return400=False)
                    cpu = httpRequest.checkVar("cpu",return400=False)
                    restart = httpRequest.checkVar("restart",return400=False)
                    result = DockerFuncs.updateContbyID(id,memory=memory,cpu=cpu,restart=restart)
                if result["success"] is True:
                    result["id"] = id
                    httpResponse.print200()
                    print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
                    exit()
                elif "already paused" in result["result"]:
                    result["result"] = "AlreadyContPaused"
                elif "is not paused" in result["result"]:
                    result["result"] = "NotContPaused"
                elif "is not running" in result["result"]:
                    result["result"] = "NotRunningCont;"
                httpResponse.print404(result["result"], action=action)

        httpResponse.print200()
        print(json.dumps({"error": True, "action":action, "return": [{"msg": "'action' is not correct! "}], }, indent=INTEND_INT))

    def network(self, queries):
        action = httpRequest.checkVar("action")
        result = None
        for case in switch(action):
            network = httpRequest.checkVar("network")
            if case("create"):
                if result is None:
                    result = DockerFuncs.network("create", network=network)
            if case("remove"):
                if result is None:
                    result = DockerFuncs.network("remove", network=network)
            if result is None:
                containername = httpRequest.checkVar("containername")
                id = DockerFuncs.issetCont(containername)
                if case("connect"):
                    result = DockerFuncs.network("connect", network=network, contname=id)
                if case("disconnect"):
                    if result is None:
                        result = DockerFuncs.network("disconnect", network=network, contname=id)
                result["id"] = id
            if result["success"] is True:
                httpResponse.print200()
                print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
                exit()

            httpResponse.print404(result["result"], action=action)
        httpResponse.print404("NotImplemented", action=action)

    def tar_export(self, queries):
        action = httpRequest.checkVar("action")
        result = None

        for case in switch(action):  # load is "container" , import is "image"
            if case("container_export"): #docker export
                if result is None:
                    containername = httpRequest.checkVar("containername")
                    filename = str(current_milli_time()) + containername
                    result = DockerFuncs.exportbyContID(containername,filename)
            if case("image_save"): #docker save
                if result is None:
                    reponame = httpRequest.checkVar("imgname")
                    tagname = httpRequest.checkVar("tagname")
                    filename = str(current_milli_time()) + reponame + tagname
                    result = DockerFuncs.exportImgByURL(filename,reponame,tagname)
            if case("mktar"):  #指定dirをtarballでローカルで固める
                if result is None:
                    containername = httpRequest.checkVar("containername")
                    dir = httpRequest.checkVar("dir")
                    filename = str(current_milli_time()) + dir + containername
                    result = DockerFuncs.getTarballbyContID(containername,dir,filename)
        if result["success"] is True:
                httpResponse.print200()
                print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
                exit()
        httpResponse.print404(result["result"], action=action)

    def tar_import(self, queries):
        action = httpRequest.checkVar("action")
        result = None
        for case in switch(action): #load is "container" , import is "image"
            if case("load_container"):
                if result is None:
                    filename = httpRequest.checkVar("filename")
                    result = DockerFuncs.loadContainer(filename=filename)
            if case("extar"):
                if result is None:
                    containername = httpRequest.checkVar("containername")
                    path = httpRequest.checkVar("dir")
                    filename = httpRequest.checkVar("filename")
                    result = DockerFuncs.extractTarBall(filename,containername=containername,path=path)
            if case("import_filepath"):
                #view-source:http://cgitest/test/httpAPI.py?page=tar_import&action=import_filepath&filename=1564495552103objectivegolick&reponame=test2&tagname=test
                if result is None:
                    reponame = httpRequest.checkVar("imgname")
                    tagname = httpRequest.checkVar("tagname")
                    filename = httpRequest.checkVar("filename")
                    result = DockerFuncs.importImgbyfilepath(filename=filename,imagename=reponame,tagname=tagname)
            if case("import_url"):
                if result is None:
                    url = httpRequest.checkVar("url")
                    reponame = httpRequest.checkVar("imgname")
                    tagname = httpRequest.checkVar("tagname")
                    result = DockerFuncs.importByURL(url,reponame,tagname)
                if result["success"] is True:
                    httpResponse.print200()
                    print(json.dumps({"error": False, "return": result}, indent=INTEND_INT))
                    exit()
                httpResponse.print404(result["result"], action=action)

    def composer(self, queries):pass #Future Feature



eachPages = eachPages()


#Main Stream

queries = httpRequest.getQueries(os.environ.get('QUERY_STRING'))
if "page" not in queries.keys():
    httpResponse.print400("Query 'page' is not setted.")

pagename = queries.get("page")[0]
print(pagename)

for case in switch(pagename):
 if case("container"):
     eachPages.container(queries)
     break
 if case("image"):
     eachPages.image(queries)
     break
 if case("network"):
     eachPages.network(queries)
     break
 if case("tar_export"):
     eachPages.tar_export(queries)
     break
 if case("tar_import"):
     eachPages.tar_import(queries)
     break
 if case("default"): pass
 if case():
    eachPages.default()
    exit()
