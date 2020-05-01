#!/usr/bin/env python3
#encoding:utf-8
from subprocess import check_output
from datetime import datetime
import pickle
import sys

script_path = "/".join(sys.argv[0].split("/")[:-1])
nettop_code = ["nettop", "-x", "-P", "-L", "1", "-k", "state,interface,rx_dupe,rx_ooo,re-tx,rtt_avg,rcvsize,tx_win,tc_class,tc_mgt,cc_algo,P,C,R,W,arch", "-t", "external"]
ps_code = ["ps", "awx", "-o", "pid,comm"]
emoji_list = ["", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
color_list = ["#1F78B4", "#D62829", "#FF7F0F", "#9467BD", "#8C574B", "#E377C3", "#7F7F7F", "#BCBD23", "#15BFD0", "#2E9F2D"]
#HTML markup
html_start = lambda fontsize: '''<html><meta charset="utf-16"><span style="color: white; font-family: Helvetica Neue; font-size:%dpx">'''%(fontsize)
html_end = '''</span></html>'''
spanTITLE = lambda color, name: '''<span style="color:%s; font-size:15px"><b>%s</b></span>'''%(color, name)
spanHIGHTLIGHT = lambda string: '''<span style="color:#34CC46">%s</span>'''%string
#Change 1e6,1e3 to 2**20,2**10 if MiB/s,KiB/s are prefered
#speed = lambda x: "%.1f MiB/s"%(x/2**20) if x>=1e6 else ("%.1f KiB/s"%(x/2**10) if x>=1e3 else "%.1f B/s"%(x))
speed = lambda x: "%.1f M/s"%(x/1e6) if x>=1e6 else ("%.1f K/s"%(x/1e3) if x>=1e3 else "%.1f B/s"%(x))

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
            data.append((" ".join(item_list[1:])).strip())
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
    #Ensure sortBy only has 2 possible values
    sortBy = "UL" if sortBy=="UL" else "DL"
    #Insert speed summary at index=0, +sortBy is for text highlight in read_mode
    result.insert(0, ["Total."+sortBy]+speed_sum)
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

def getIconPath(ProcessPath):
    #Get process's default icon path or use generitc icons if not found
    if ".app" in ProcessPath:
        import plistlib
        App_root = ProcessPath.split(".app")[0]+".app"
        try:
            info_path = App_root + "/Contents/Info.plist"
            icon_name = plistlib.load(open(info_path, "rb"))["CFBundleIconFile"]
            #Note that the icon_name is not always with .icns suffix, e.g. Mail.app 
            icon_path = App_root + "/Contents/Resources/" + (icon_name if ".icns" in icon_name else icon_name+".icns")
        except:
            icon_path = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns"
    elif ".framework" in ProcessPath:
        icon_path = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/KEXT.icns"
    else:
        icon_path = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/ExecutableBinaryIcon.icns"
    
    return icon_path

def format_data(data, infoType, sortBy, index):
    '''
    if infoType == "app", return JSON with icon path and process name
    if infoType =="speed", return JSON with html markup speed info
    '''
    data = data[index]
    if infoType == "app":
        icon_path = getIconPath(data[0]) if index != 0 else ""
        #Format process name
        raw_name = data[0].split("/")[-1].strip()
        delimiter = "." if "." in raw_name else " "
        process_name_list = (raw_name).split(delimiter)
        NumOfWords = len(process_name_list)
        if NumOfWords == 1:
            NameLength = len(raw_name)
            if NameLength > 25:
                # If the name is too long
                process_name = raw_name[:-(-NameLength//2)] + "-\n" + raw_name[-(-NameLength//2):]
                font_size = 11
            else:
                process_name = process_name_list[0]
                font_size = 14
        else:
            process_name = delimiter.join(process_name_list[:-(-NumOfWords//2)]) + ("." if delimiter=="." else "") + "\n" + delimiter.join(process_name_list[-(-NumOfWords//2):])
            font_size = 11
        #Return JSON string
        return jsonfy(text=process_name, icon_path=icon_path, font_size=font_size)

    elif infoType == "speed":
        DLspeed = "▼" + speed(data[1])
        ULspeed = "▲" + speed(data[2])
        speed_string = spanHIGHTLIGHT(ULspeed)+'''<br>'''+DLspeed if sortBy == "UL" else ULspeed+'''<br>'''+spanHIGHTLIGHT(DLspeed)
        text = html_start(11) + speed_string + html_end
        return jsonfy(text=text)
    else:
        print("Unknown info type")

def format_data_simple(data, sortBy):
    '''
    Simply concatenate top 10 items into a string
    '''
    if sortBy == "DL":
        text = " | ".join([spanTITLE(color, emoji_num+sublist[0].split("/")[-1]) + spanHIGHTLIGHT(" ▼" + speed(sublist[1])) + " ▲" + speed(sublist[2]) for emoji_num, color, sublist in zip(emoji_list, color_list, data)])
    else:
        text = " | ".join([spanTITLE(color, emoji_num+sublist[0].split("/")[-1]) + " ▼" + speed(sublist[1]) + spanHIGHTLIGHT(" ▲" + speed(sublist[2])) for emoji_num, color, sublist in zip(emoji_list, color_list, data)])
    
    text = html_start(12) + text + html_end
    return jsonfy(text=text)
    
def format_data_simple_icon(data, sortBy, index):
    '''
    Get icon path, name and speed of A process at once, at cost of one-line display
    '''
    data = data[index]
    color = color_list[index]
    
    processName = spanTITLE(color, data[0].split("/")[-1].strip())
    DLspeed = " ▼" + speed(data[1])
    ULspeed = " ▲" + speed(data[2])
    speed_string = DLspeed+spanHIGHTLIGHT(ULspeed) if sortBy == "UL" else spanHIGHTLIGHT(DLspeed)+ULspeed
    text = html_start(12)+processName+speed_string+html_end
    
    icon_path = getIconPath(data[0]) if index != 0 else ""
    return jsonfy(text=text, icon_path=icon_path)

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
            #Save calculated network speed data in local file, so that no calculation is needed in read_mode
            pickle.dump(data, open(script_path+"/NetStatus/data", 'wb'))
        except:
            #Get new info and re-create file if file not found or data structure is unknown
            getInfo_dumpVal()

    elif "read_mode" in argv_dict:
        try:
            data = pickle.load(open(script_path+"/NetStatus/data", 'rb'))
            sortBy = data[0][0].split(".")[-1]
            data[0][0] = "Total"
            
            if argv_dict["read_mode"] == "simple":
                return format_data_simple(data, sortBy)
            
            elif argv_dict["read_mode"] == "simple_icon":
                if "index" in argv_dict:
                    #Get info of index-th process
                    index = min(len(data)-1, int(argv_dict["index"]))
                    return format_data_simple_icon(data, sortBy, index)
                
            elif argv_dict["read_mode"] == "rich":
                if ("index" in argv_dict) and ("infoType" in argv_dict):
                    index = min(len(data)-1, int(argv_dict["index"]))
                    #infoType = "app" or "speed"
                    infoType = argv_dict["infoType"]      
                    
                    return format_data(data, infoType, sortBy, index)
        except:
            #Error indicates the data is not ready yet
            return jsonfy(text="Gathering Data")
    else:
        print("Invalid arguments")


if __name__ == '__main__':
    print(main())
