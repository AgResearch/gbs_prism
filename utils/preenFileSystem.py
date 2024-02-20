#!/usr/bin/python

from types import *
import os
import sys
import re
import csv

 
def main():
    """
    this script summarises the file types in a file system
    """
 
    # parse o.l. args
    if len(sys.argv) < 2:
        raise Exception("usage : python preenFileSystem.py rootdir")

    argDict = dict([ re.split('=',arg) for arg in sys.argv if re.search('=',arg) != None ])
    print "using %s"%str(argDict)

    root=sys.argv[1]

    if not os.path.exists(root):
        raise Exception("%s does not exist"%root)

    if not os.path.isdir(root):
        raise Exception("%s is not a directory"%root)


    # this one does diffs
    #walkFileSystem(root,diffCopies,"/mnt/datacopy")
    #return

    # the usual section...
    stats = {}
    walkFileSystem(root,summariseTypes,stats)
    #print stats
    print "\n\n\nRESULTS:\n"
    records = ["%s\t%s"%(entry[0], reduce(lambda x,y:"%s\t%s"%(x,y), entry[1].values())) for entry in stats.items()]
    for record in records:
       print record
    return

    # the section for generating a command file 
    #commands = {".pif" : [], ".wells" : [], ".GB" : []}
    #commands = {".pRBC" : [], ".bbcSelfLearn" : [], ".postKeyReScaled" : [], ".cafieCorrected" : [], ".wellBasedNukeInterpolated" : [], ".backSubMLE" : [], ".balanced" : []}
    #commands = {".afg" : []}

    #walkFileSystem(root,genArchiveTypes,commands)
    #print stats
    #for commandarray in commands.values():
    #    for command in commandarray:
    #        print command

    #return


def walkFileSystem(root, func, args = None):
    os.path.walk(root,func,args)


def listFolder(args, dirname, names):
    print dirname
    print names

def diffCopies(copydir, dirname, names):
    for name in names:
        fullname = os.path.join(dirname,name)
        copyname = os.path.join(copydir,fullname)
        #print "comparing %s with %s\n"%(fullname, copyname)
        if not os.path.exists(copyname):
            if os.path.islink(copyname):
               print "brokenlink : %s"%fullname
            else:
               print "notthere : %s"%fullname
        elif os.path.isfile(fullname):
            (origmtime, origsize) = (os.path.getmtime(fullname), os.path.getsize(fullname)) 
            (copymtime, copysize) = (os.path.getmtime(copyname), os.path.getsize(copyname))
            #print "%s : %s %s"%(fullname, str((origmtime, origsize)), str((copymtime, copysize)))
            if (origmtime, origsize) == (copymtime, copysize):
                print "same : %s"%fullname
            else:
                print "different : %s"%fullname

        

def summariseTypes(summary, dirname, names):
    for name in names:
        fullname = os.path.join(dirname,name)
     
        if not os.path.islink(fullname):
            (prefix, suffix) = os.path.splitext(name)
            try:
                if suffix not in summary:
                    summary[suffix] = {"count" : 1, "size" : os.path.getsize(fullname)}
                else:
                    summary[suffix]["count"] += 1
                    summary[suffix]["size"]  += os.path.getsize(fullname)
            except OSError, msg:
                print msg

def genArchiveTypes(commands, dirname, names):
    for name in names:
        fullname = os.path.join(dirname,name)

        if not os.path.islink(fullname):
            (prefix, suffix) = os.path.splitext(name)
            if suffix  in commands:
                placeholder = "%s.__placeholder__original__deleted__"%fullname
                if os.path.exists(placeholder):
                    print "Warning : skipped %s as %s already exists"%(fullname, placeholder)
                    continue
                command = "ls -l %s > %s"%(fullname, placeholder)
                commands[suffix].append(command)
                command = "rm -f %s"%fullname
                commands[suffix].append(command)
              



if __name__ == "__main__" :
    main()
