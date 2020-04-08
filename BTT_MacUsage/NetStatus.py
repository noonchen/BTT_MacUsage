#!/usr/bin/env python3
#encoding:utf-8
from subprocess import check_output
from datetime import datetime
import pickle
import sys

script_path = "/".join(sys.argv[0].split("/")[:-1])
nettop_code = ["nettop", "-x", "-P", "-L", "1", "-k", "state,interface,rx_dupe,rx_ooo,re-tx,rtt_avg,rcvsize,tx_win,tc_class,tc_mgt,cc_algo,P,C,R,W,arch", "-t", "external"]
ps_code = ["ps", "awx", "-o", "pid,comm"]

def parseInfo(string, Info="net"):
    '''
    Convert shell results to dictionary, use PID as key
    '''
    L = string.strip().split('\n')[1:]
    pid = []
    data = []
    if Info == 'net':
        for item in L:
            item_list = item.split(",")
            pid.append(item_list[1].split(".")[-1])
            data.append([item_list[0]]+item_list[2:4])
    else:
        for item in L:
            item_list = item.strip().split(" ")
            pid.append(item_list[0])
            data.append(" ".join(item_list[1:]))
    return dict(zip(pid, data))

def calNetSpeed(prev, new, sortBy="UL"):
    '''
    Calculate DL/UL speed by ΔBytes/Δtime
    Sort the list by download ("DL") or upload (UL) speed in descending
    '''
    prev_dict = parseInfo(prev)
    new_dict = parseInfo(new)
    process_dict = parseInfo(check_output(ps_code).decode('utf-8'), Info="path")

    speed_sum = [0, 0]
    result = []
    for pid in prev_dict:
        if (pid in new_dict) and (pid in process_dict):
            prev_data = prev_dict[pid]
            new_data = new_dict[pid]

            delta_time = (datetime.strptime(new_data[0],"%H:%M:%S.%f") - datetime.strptime(prev_data[0],"%H:%M:%S.%f")).total_seconds()
            net_speed = [max(float(n)-float(p), 0)/delta_time for n, p in zip(new_data[1:], prev_data[1:])]

            speed_sum = [i+j for i, j in zip(speed_sum, net_speed)]
            result.append([process_dict[pid]]+net_speed)

    result.sort(key=lambda x:x[2 if sortBy=="UL" else 1], reverse=True)
    result.insert(0, ["Total"]+speed_sum)
    return result

def getInfo_dumpVal():
    '''
    Get new info from nettop, then save to local file "NetStatus_savedInfo"
    It's more efficient than saving to BTT variables which needs to run Applescript
    '''
    new_info = check_output(nettop_code).decode('utf-8')
    #check_output(["osascript", "-e", 'tell application "BetterTouchTool" to set_string_variable "NetTraffic" to "%s"'%(new_info)])
    pickle.dump(new_info, open(script_path+"/NetStatus/savedInfo", 'wb'))
    return new_info

def jsonfy(text="", icon_data="", icon_path="", background_color="", font_color="", font_size=0):
    '''
    Convert data into JSON string for BTT to render
    '''
    import json
    dict = {}
    if text != "": dict["text"] = text
    if icon_data != "": dict["icon_data"] = icon_data
    if icon_path != "": dict["icon_path"] = icon_path
    if background_color != "": dict["background_color"] = background_color
    if font_color != "": dict["font_color"] = font_color
    if font_size != 0: dict["font_size"] = font_size

    return json.dumps(dict, ensure_ascii=False)

def format_data(data, infoType):
    '''
    1. Get application/process icon path by its location
    2. Get application/process name and break it into two lines if space is detect, e.g. Google Chrome Helper
    3. Convert unit from Byte/s to M/s (K/s) based on the value
    '''
    if infoType == "app":
        #Get process's default icon path or use generitc icons if not found
        if ".app" in data[0]:
            import plistlib
            App_root = data[0].split(".app")[0]+".app"
            try:
                info_path = App_root + "/Contents/Info.plist"
                icon_name = plistlib.load(open(info_path, "rb"))["CFBundleIconFile"]
                #Note that the icon_name is not always with .icns suffix, e.g. Mail.app 
                icon_path = App_root + "/Contents/Resources/" + (icon_name if ".icns" in icon_name else icon_name+".icns")
            except:
                icon_path = script_path+"/icons/GenericApplicationIcon.icns"
        elif ".framework" in data[0]:
            icon_path = script_path+"/icons/KEXT.icns"
        else:
            icon_path = script_path+"/icons/ExecutableBinaryIcon.icns"
        #Format process name
        process_name_list = (data[0].split("/")[-1].strip()).split(" ")
        NumOfWords = len(process_name_list)
        if NumOfWords == 1:
            process_name = process_name_list[0]
            font_size = 14
        else:
            process_name = " ".join(process_name_list[:-(-NumOfWords//2)]) + "\n" + " ".join(process_name_list[-(-NumOfWords//2):])
            font_size = 11
        #Return JSON string
        return jsonfy(text=process_name, icon_path=icon_path, font_size=font_size)

    elif infoType == "speed":
        #Change 1e6,1e3 to 2**20,2**10 if MiB/s,KiB/s are prefered
        speed = lambda x: "%.1f M/s"%(x/1e6) if x>=1e6 else ("%.1f K/s"%(x/1e3) if x>=1e3 else "%.1f B/s"%(x))
        DLspeed = "↓" + speed(data[1])
        ULspeed = "↑" + speed(data[2])
        return jsonfy(text=ULspeed+"\n"+DLspeed, font_size=11)
    else:
        print("Unknown info type")

def format_data_simple(data):
    '''
    Simply concatenate top 10 items into a string
    '''
    emoji_list = ["", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    speed = lambda x: "%.1f M/s"%(x/1e6) if x>=1e6 else ("%.1f K/s"%(x/1e3) if x>=1e3 else "%.1f B/s"%(x))
    text = " | ".join([emoji_num+sublist[0].split("/")[-1].strip() + " ▼" + speed(sublist[1]) + " ▲" + speed(sublist[2]) for emoji_num, sublist in zip(emoji_list, data)][:11])
    return jsonfy(text=text)
    
def main():
    #Parse arguments into dict
    argv_dict = {}
    for argv in sys.argv:
        if argv.startswith("-"):
            arg, val = argv.strip("-").split("=")
            argv_dict[arg] = val

    if "sortBy" in argv_dict:
        #Calculate speed only if given argument "sortBy"
        try:
            #Load previous info from local file
            prev_info = pickle.load(open(script_path+"/NetStatus/savedInfo", 'rb'))
            #Get new info from nettop
            new_info = getInfo_dumpVal()
            data = calNetSpeed(prev_info, new_info, sortBy=argv_dict["sortBy"])
            pickle.dump(data, open(script_path+"/NetStatus/data", 'wb'))
        except:
            #Get new info and re-create file if file not found or data structure is unknown
            getInfo_dumpVal()

    elif "read_mode" in argv_dict:
        try:
            data = pickle.load(open(script_path+"/NetStatus/data", 'rb'))
            
            if argv_dict["read_mode"] == "simple":
                return format_data_simple(data)
            
            elif argv_dict["read_mode"] == "rich":
                if ("index" in argv_dict) and ("infoType" in argv_dict):
                    #Get info of index-th process
                    index = int(argv_dict["index"])
                    #infoType = "app" or "speed"
                    infoType = argv_dict["infoType"]      
                    
                    requested_data = data[min(len(data)-1, index)]
                    return format_data(requested_data, infoType)
        except:
            #Error indicates the data is not ready yet
            return jsonfy(text="Gathering Data")
    else:
        print("Invalid arguments")


if __name__ == '__main__':
    print(main())
