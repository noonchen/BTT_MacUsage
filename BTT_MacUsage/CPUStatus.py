#!/usr/bin/env python3
#encoding:utf-8
from subprocess import check_output
import pickle
import sys

script_path = "/".join(sys.argv[0].split("/")[:-1])
ps_code = ["ps", "awx", "-o", "ppid,pid,pcpu,comm"]
emoji_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
color_list = ["#D62829", "#1F78B4", "#FF7F0F", "#9467BD", "#8C574B", "#E377C3", "#7F7F7F", "#BCBD23", "#15BFD0", "#2E9F2D"]
#HTML markup
html_start = lambda fontsize: '''<html><meta charset="utf-16"><span style="color: white; font-family: Helvetica Neue; font-size:%dpx">'''%(fontsize)
html_end = '''</span></html>'''
spanTITLE = lambda color, name: '''<span style="color:%s; font-size:15px"><b>%s</b></span>'''%(color, name)
spanHIGHTLIGHT = lambda string: '''<span style="color:#34CC46">%s</span>'''%string
boolean = lambda string: True if string=="True" else False

def parseInfo(raw_data, showChildProcess):
    dic = {}
    rawList = raw_data.strip().split("\n")[1:]
    
    if showChildProcess:
        for line in rawList:
            line_list = line.strip().split()
            line_list = line_list[:3] + [" ".join(line_list[3:])]
            #line_list = [ppid, pid, pcpu, comm]
            #dic[pid] = [pcpu, comm, childNo.]
            dic[line_list[1]] = [float(line_list[2]), line_list[3], 0]
    else:
        for line in rawList[::-1]:
            line_list = line.strip().split()
            line_list = line_list[:3] + [" ".join(line_list[3:])]

            if line_list[0] != "1":
                #current process is child of other process
                if (not line_list[0] in dic) and (not line_list[1] in dic):
                    #current process has no child, its parent is not in dictionary
                    dic[line_list[0]] = [float(line_list[2]), line_list[3], 1]
                elif (not line_list[0] in dic) and (line_list[1] in dic):
                    #current process has child(s), its parent is not in dictionary
                    dic[line_list[0]] = [dic[line_list[1]][0]+float(line_list[2]), line_list[3], 1 + dic[line_list[1]][2]]
                    #remove current process from dic, it won't have any child process anymore 
                    dic.pop(line_list[1])
                elif (line_list[0] in dic) and (not line_list[1] in dic):
                    #current process has no child, its parent is in dictionary
                    dic[line_list[0]] = [dic[line_list[0]][0]+float(line_list[2]), dic[line_list[0]][1], 1 + dic[line_list[0]][2]]
                elif (line_list[0] in dic) and (line_list[1] in dic):
                    #current process has child(s), its parent is in dictionary
                    dic[line_list[0]] = [dic[line_list[0]][0]+dic[line_list[1]][0]+float(line_list[2]), dic[line_list[0]][1], 1 + dic[line_list[1]][2] + dic[line_list[0]][2]]
                    #remove current process from dic
                    dic.pop(line_list[1])

            else:
                #current process's parent is launchd
                #It's treated as top-level process in our calculation
                if line_list[1] in dic:
                    #it's already in the dictionary
                    dic[line_list[1]] = [dic[line_list[1]][0]+float(line_list[2]), line_list[3], dic[line_list[1]][2]]
                else:
                    dic[line_list[1]] = [float(line_list[2]), line_list[3], 0]
    data_list = [[pid]+dic[pid] for pid in dic]
    # [pid, pcpu, comm, childNo.]
    data_list.sort(key=lambda x:x[1], reverse=True)
    return data_list

def get_PS_result(showChildProcess=True):
    '''
    When showChildProcess = False, only parent process under launchd 
    will be displayed and the CPU usage is the sum of the usage of all the child processes
    '''
    ps_result = check_output(ps_code).decode('utf-8')
    result = parseInfo(ps_result, showChildProcess)
    return result

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

# ----------------------------------

def format_data(data, infoType, showChildProcess, index):
    '''
    if infoType == "app", return JSON with icon path and process name
    if infoType =="cpu", return JSON with html markup cpu info
    '''
    data = data[index]
    if infoType == "app":
        icon_path = getIconPath(data[2])
        #Format process name
        raw_name = data[2].split("/")[-1].strip()
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
            process_name = delimiter.join(process_name_list[:NumOfWords//2]) + ("." if delimiter=="." else "") + "\n" + delimiter.join(process_name_list[NumOfWords//2:])
            font_size = 11
        
        #Return JSON string
        return jsonfy(text=process_name, icon_path=icon_path, font_size=font_size)

    elif infoType == "cpu":
        Line1 = "%CPU: " + spanHIGHTLIGHT("%.1f"%(data[1])+"%")
        Line2 = "PID: " + spanHIGHTLIGHT(str(data[0])) if showChildProcess else "#child: " + spanHIGHTLIGHT(str(data[3]))
        text = html_start(11) + Line1 +'''<br>'''+ Line2 + html_end
        return jsonfy(text=text)
    else:
        print("Unknown info type")

def format_data_simple(data, showChildProcess, onlyCPU):
    '''
    Simply concatenate top 10 items into a string
    '''
    if onlyCPU:
        text = " | ".join([spanTITLE(color, emoji_num+sublist[2].split("/")[-1]) + " %CPU: " + spanHIGHTLIGHT("%.1f"%(sublist[1])+"%") for emoji_num, color, sublist in zip(emoji_list, color_list, data)])
    else:
        if showChildProcess:
            text = " | ".join([spanTITLE(color, emoji_num+sublist[2].split("/")[-1]) + " %CPU: " + spanHIGHTLIGHT("%.1f"%(sublist[1])+"%") + " PID: " + spanHIGHTLIGHT(str(sublist[0])) for emoji_num, color, sublist in zip(emoji_list, color_list, data)])
        else:
            text = " | ".join([spanTITLE(color, emoji_num+sublist[2].split("/")[-1]) + " %CPU: " + spanHIGHTLIGHT("%.1f"%(sublist[1])+"%") + " #child: " + spanHIGHTLIGHT(str(sublist[3])) for emoji_num, color, sublist in zip(emoji_list, color_list, data)])
        
    text = html_start(12) + text + html_end
    return jsonfy(text=text)
    
def format_data_simple_icon(data, showChildProcess, onlyCPU, index):
    '''
    Get icon path, name and cpu of A process at once, at cost of one-line display
    '''
    data = data[index]
    color = color_list[index]
    
    processName = spanTITLE(color, data[2].split("/")[-1].strip())
    cpu_info = " %CPU: " + spanHIGHTLIGHT("%.1f"%(data[1])+"%")
    pid_info = " PID: " + spanHIGHTLIGHT(str(data[0])) if showChildProcess else "#child: " + spanHIGHTLIGHT(str(data[3]))
    info_string = cpu_info if onlyCPU else cpu_info+pid_info
    text = html_start(12)+processName+info_string+html_end
    
    icon_path = getIconPath(data[2])
    return jsonfy(text=text, icon_path=icon_path)

def main():
    #Parse arguments into dict
    argv_dict = {}
    for argv in sys.argv:
        if argv.startswith("-"):
            arg, val = argv.strip("-").split("=")
            argv_dict[arg] = val
    # argv_dict = {"showChildProcess":"False", "index":"1", "infoType":"app"}
    if "showChildProcess" in argv_dict:
        showChildProcess=boolean(argv_dict["showChildProcess"])
        data = get_PS_result(showChildProcess=showChildProcess)
        pickle.dump([showChildProcess, data], open(script_path+"/CPUStatus/data", 'wb'))
        return showChildProcess

    elif "read_mode" in argv_dict:
        try:
            [showChildProcess, data] = pickle.load(open(script_path+"/CPUStatus/data", 'rb'))
            onlyCPU = boolean(argv_dict["onlyCPU"]) if "onlyCPU" in argv_dict else False
            
            if argv_dict["read_mode"] == "simple":
                return format_data_simple(data, showChildProcess, onlyCPU)
            
            elif argv_dict["read_mode"] == "simple_icon":
                if "index" in argv_dict:
                    #Get info of index-th process
                    index = min(len(data)-1, int(argv_dict["index"]))
                    return format_data_simple_icon(data, showChildProcess, onlyCPU, index)
                
            elif argv_dict["read_mode"] == "rich":
                if ("index" in argv_dict) and ("infoType" in argv_dict):
                    index = min(len(data)-1, int(argv_dict["index"]))
                    #infoType = "app" or "cpu"
                    infoType = argv_dict["infoType"]      
                    
                    return format_data(data, infoType, showChildProcess, index)
        except:
            #Error indicates the data is not ready yet
            return jsonfy(text="Gathering Data")
        
    elif "kill_process" in argv_dict:
        try:
            index = int(argv_dict["kill_process"])
            [showChildProcess, data] = pickle.load(open(script_path+"/CPUStatus/data", 'rb'))
            PID = data[index][0]
            processName = data[index][2].split("/")[-1].strip()
            decision = check_output(["osascript", 
                          "-e", 
                          '''tell application "System Events" to get button returned of (display alert "Force quiting this process\n%s" message "Be sure to save all your works, there's no turning back!" as critical buttons {"MERCY", "KILL"} default button "MERCY")'''%processName]).decode('utf-8').strip()
            if decision == "KILL":
                check_output(["kill", "-9", PID])
        except:
            print("Something's wrong")
    else:
        print("Invalid arguments")

if __name__ == "__main__":
    print(main())

