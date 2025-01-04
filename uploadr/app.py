from flask import Flask, request, redirect, url_for, render_template, make_response, send_file
import os, time
import json
import glob
import re #정규표현식 (파일이름 수정을 위함)
from uuid import uuid4
from requests import get
from collections import OrderedDict
import codecs

app = Flask(__name__)

static_file_save_dir = "uploadr/static/uploads"
static_file_save_dir_wout_root = "static/uploads"

cwd=os.getcwd()
service_path="http://localhost:2006"
download_path = "attachments"
prohibited_file_name = ["IMH_File_uploaderinfo.txt","IMH_File_Downloaderinfo.txt"]
print("Service Started.")
print("Working Dir = " + cwd + ", file_save_dir= " + static_file_save_dir )



######## 업로드 페이지 핸들링 시작 ########
@app.route("/")
def index():
	return render_template("index.html")
######## 업로드 페이지 핸들링 끝 ########

######## 파일 UPLOAD 받는 로직 시작 ########
@app.route("/upload", methods=["POST"])
def upload(): #Handle the upload of a file.
	form = request.form
	
	'''
	print("=== Form Data Begin ===")
	for key, value in list(form.items()):
		print(key, "=>", value)
	print("=== Form Data End ===")
	'''
	
	## 순서 : 
	#		1) 사용자 입력 파싱 및 사용자 정보 확인
	#		2) UUID생성
	#		3) 폴더생성
	#		4) 파일저장
	#		5) 
	
	#### 사용자 입력 파싱 시작 ####
	client_Upload_OP		 = form.get("Upload_OP", "None")	# * Upload OP# [Upload_OP]
	client_Server			 = form.get("Server", "None")		# * 업로드 서버 [Server]		- cdn1.cntc(단일)
	client_name_type		 = form.get("name_type", "REPL")	# * 파일 이름 규칙[name-type]	- REPL(한글/공백 제거하고 파일이름 보전)
	#														      - RAND(확장자만 남기고 랜덤)	- ORIG(파일이름 무조건 보전)
	client_link_type		 = form.get("link_type", "Discord")        # * 링크 생성 타입 [link_type]	- Discord(디스코드 타입)
	#														      - Long(긴 UUID타입)			- Short(짧은 타입)
	client_File_Description  = form.get("File_Description", "None") # Note(파일 설명) [File_Description]
	client_is_ajax           = form.get("__ajax", None)		    # ajax여부
	if client_is_ajax == "true": # ajax를 통한 Req인지를 파악한다.
		is_ajax = True
	else:
		is_ajax = False	
	
	client_user_ipaddr1		 = str(request.remote_addr)
	try:
		client_user_ipaddr2	 = str(request.environ.get('HTTP_X_REAL_IP', request.remote_addr))
	except:
		client_user_ipaddr2  = "RAW"
	client_user_ipaddr = client_user_ipaddr1 + "(" + client_user_ipaddr2 + ")"
	
	try:
		client_user_agent	 = str(request.headers.get('User-Agent')) + "(RAW-UA)"
	except:
		client_user_agent    = "NA"
	
	
	#### 사용자 입력 파싱 끝.  ####
	
	
	#### UUID(업로드 폴더) 생성기 시작 ####
	try_count=0
	while True: # 사용자 입력에 따라 타입에 맞는 경로 생성, 정상 생성 확인되면 break하여 그대로 진행, 중복일시 재실행, 100번이상 재실행 감지시 중단.
		try_count = try_count +1
		if client_link_type == "Discord": #디스코드 타입
			upload_key1 = str(uuid4().int)[:19] # 첫번째 디렉터리
			upload_key2 = str(uuid4().int)[:19] # 디렉터리 안에 들어가는, 두번째 디렉터리
			upload_key  = upload_key1 + "/" + upload_key2
		elif client_link_type == "Long": #Long 타입
			upload_key1 = str(uuid4().int)  # 첫번째 디렉터리
			upload_key2 = str(uuid4().int)  # 디렉터리 안에 들어가는, 두번째 디렉터리
			upload_key  = upload_key1 + "/" + upload_key2
		elif client_link_type == "Short": #쇼트 타입
			upload_key1 = str(uuid4().int)[:5]  # 첫번째 디렉터리
			upload_key2 = str(uuid4().int)[:5]  # 디렉터리 안에 들어가는, 두번째 디렉터리
			upload_key  = upload_key1 + "/" + upload_key2
		else:
			if is_ajax:
				return ajax_response(False, "link_type not valid")
			else:
				return "link_type not valid"
		# Make Target dir PATH
		target_path = static_file_save_dir + "/" + upload_key
		if not os.path.exists(upload_key1):    # 중복디렉토리 검사는 첫번째 디렉토리로만 수행.
			#print("path가 중복되지 않아 정상 진행됩니다")
			break
		else:
			if try_count < 100:
				print("Path가 중복되어 다른 path를 생성합니다. " + target_path + " 의 upload_key1이 이 이미 존재합니다.")
			else:
				print("path가 고갈되었습니다")
				if is_ajax:
					return ajax_response(False, "No_Path_Left. Path가 고갈되었습니다.")
				else:
					return "No_Path_Left. Path가 고갈되었습니다."
	#### UUID(업로드 폴더) 생성기 끝. ####
	
	
	#### 경로를 바탕으로 폴더 생성 시작 ####
	try:
		os.makedirs(target_path) #폴더안에 폴더가 있어도 폴더를 한번에 생성
	except Exception as e:
		if is_ajax:
			print(e)
			return ajax_response(False, "Couldn't create upload directory: {}".format(target_path))
		else:
			print(e)
			return "Couldn't create upload directory: {}".format(target_path)
	#### 폴더 생성 끝. ####
	
	print("file UIDs : " + upload_key )
	
	#### 파일 저장을 위한 절차 시작 ####
	for upload in request.files.getlist("file"):
		filename_orig = upload.filename.rsplit("/")[0]
		
		#### > 파일이름 생성기 시작 ####
		if client_name_type == "REPL": #REPL : Discord Type filename
			filename_task = filename_orig
			filename_task = filename_task.replace(" ","_") #공백을 언더바로 치환
			filename_task = re.sub(r"[^a-zA-Z0-9_.()]","",filename_task) #영어랑 숫자 아닌거 전부 없애기
			#print(filename_task)
			if os.path.splitext(filename_task)[1] == "": #파일이름이 아예 통째로 없어졌으면
				#print("filename too short. adding random")
				filename_task = str(uuid4().hex)[:16] + filename_task #파일이름을 랜덤하게 정해서 확장자 앞에 붙여준다.
		elif client_name_type == "RAND": #RAND : Random Type filename (But do not change Extension)
			filename_task = filename_orig
			filename_task = str(uuid4().hex)[:16] + os.path.splitext(filename_task)[1] #파일이름은 랜덤, 기존 파일이름에서 확장자를 추출해서 새로운 파일이름에 갖다붙인다.
		elif client_name_type == "ORIG":
			filename_task = filename_orig
		else : # Same as "REPL" : Discord Type filename
			filename_task = filename_orig
			filename_task = filename_task.replace(" ","_") #공백을 언더바로 치환
			filename_task = re.sub(r"[^a-zA-Z0-9_.]","",filename_task)
			if os.path.splittext(filename_task) == "": #파일이름이 없어졌으면
				filename_task = str(uuid4().hex)[:16] + filename_task #파일이름을 랜덤하게 정해서 확장자 앞에 붙여준다.
		#### > 파일이름 생성기 끝 ####
		
		save_filename = filename_task #일단 1차적으로 저장할 파일이름(save_filename)을 생성된 파일이름(filename_task)으로 정한다.
		
		#### > 파일이름 중복확인 시작 ####
		filename_retry = 1
		while os.path.exists(target_path + "/" + save_filename) == True:
			filename_addr = "(" + str(filename_retry) + ")"
			save_filename = os.path.splitext(filename_task)[0] + filename_addr + os.path.splitext(filename_task)[1]
		#### > 파일이름 중복확인 끝 ####
		
		filename = save_filename #최종 저장할 파일 이름 : filename
		
		
		#### 파일 저장 시작 ####
		#destination = static_file_save_dir + "/" + upload_key + "/" + filename
		destination = target_path + "/" + filename
		
		print("Accept incoming file \"", filename_orig + "\" -> \"" + filename + "\"")
		upload.save(destination)
		#### 파일 저장 끝 ####
	
	#### 파일 저장을 위한 절차 끝. ####
	
	#### 스크립트 끝, 리턴처리 ####
	if is_ajax:
		return ajax_response(True, upload_key)
	else:
		return redirect(url_for("upload_complete", uuid=upload_key))
######## 파일 UPLOAD 받는 로직 끝 ########

######## 파일리스트 조회 로직 ########
# Note1 : 파일 조회 경로(/filecheck/ ) 변경 시, static/filecheck/uploadr.js 파일에서
# NEXT_URL 변수(상수) 변경 필요( var NEXT_URL   = "/filecheck/"; )

#### 파일리스트 조회(B타입) 시작 ####
@app.route("/filecheck/<uuid1>/<uuid2>") #link_type = Discord Type일 때.
def view_filelist_type_B(uuid1,uuid2):
	# Get their files.
	root = static_file_save_dir + "/" + uuid1 + "/" + uuid2
	if not os.path.isdir(root):
		return no_page_404_xml("view_filelist_type_B " + uuid1 + "/" + uuid2)
		#return "Error: UUID not found!"
	
	files = []
	for file in glob.glob("{}/*.*".format(root)):
		fname = file.split(os.sep)[-1]
		files.append(fname)
	
	file_linkbox_list = ""
	filelink_list = []
	for filename_now in files:
		link_now = service_path + "/" + download_path + "/" + uuid1 + "/" + uuid2 + "/" + filename_now
		filelink_list.append(link_now)
		file_linkbox_list = link_now + "\n"
		#print(file_linkbox_list)
	
	return render_template("files.html",
		uuid=uuid1 + "/" + uuid2,
		files=filelink_list,
		filelink_list_all = file_linkbox_list
	)
#### 파일리스트 조회(B타입) 끝 ####
######## 파일리스트 조회 로직 끝 ########

######## 파일다운로드 로직 시작 ########
#### 파일 다운로드(B타입) 시작 ####
@app.route("/attachments/<uuid1>/<uuid2>/<filename>") #link_type = Long 또는 Short Type일 때.
def view_or_download_file_type_A(uuid1,uuid2,filename):
	# Get their files.
	#filepath = static_file_save_dir_wout_root + "/" + uuid1 + "/" + uuid2 + "/" + filename
	filepath = cwd + "/" + static_file_save_dir + "/" + uuid1 + "/" + uuid2 + "/" + filename #자꾸 에러가 나므로 절대경로 강제지정.
	if not os.path.isfile(filepath):
		if (request.args.get("is",None)!= None)and(request.args.get("ex",None)!= None)and(request.args.get("hm",None)!= None):
			try:
				discord_cdnlink_ex = int(str(request.args.get("ex","")),16) #ex값(expire)을 추출해온다. 한번에 integer형으로 추출한다.
				if (discord_cdnlink_ex+60 < int(time.time())): # 이미 Expired되었거나 Expire가 임박(60초이내)한 경우
					return no_page_404_xml(request.url)
				print("Getting File from Discord Server")
				res_path = "https://cdn.discordapp.com" + request.full_path
				return redirect(res_path)
			except Exception as e:
				return no_page_404_xml(request.url)
		else:
			return no_page_404_xml(request.url)
		
	
	client_user_ipaddr1		 = str(request.remote_addr)
	try:
		client_user_ipaddr2	 = str(request.environ.get('HTTP_X_REAL_IP', request.remote_addr))
	except:
		client_user_ipaddr2  = "RAW"
	client_user_ipaddr = client_user_ipaddr1 + "(" + client_user_ipaddr2 + ")"
	
	try:
		client_user_agent	 = str(request.headers.get('User-Agent')) + "(RAW-UA)"
	except:
		client_user_agent    = "NA"
	
	try:
		ext = filename.split(".")[-1].lower()
	except:
		ext = ""
	
	
	if ext == "jpg" or ext == "jpeg" :
		mine_type_str = "image/jpeg"
	elif ext == "png" :
		mine_type_str = "image/png"
	elif ext == "bmp" :
		mine_type_str = "image/x-ms-bmp"
	elif ext == "ico" :
		mine_type_str = "image/x-icon"
	elif ext == "svg" :
		mine_type_str = "image/svg+xml"
	
	elif ext == "txt" :
		mine_type_str = "text/plain"
	
	elif ext == "mp3" :
		mine_type_str = "audio/mpeg"
	elif ext == "wav" :
		mine_type_str = "audio/vnd.wav"
	elif ext == "wma" :
		mine_type_str = "audio/x-ms-wma"
	
	
	elif ext == "mp4" :
		mine_type_str = "video/mp4"
	elif ext == "webm":
		mine_type_str = "video/webm"
	elif ext == "mkv":
		mine_type_str = "video/x-matroska"
	elif ext == "wmv":
		mine_type_str = "video/x-ms-wmv"
	
	else:
		mine_type_str = "application/octet-stream"
	
	
	
	if (mine_type_str == "application/octet-stream"):
		return send_file(filepath, as_attachment=True)
	else:
		return send_file(filepath, mimetype=mine_type_str)
	return send_file(filepath, as_attachment=True)
#### 파일 다운로드(B타입) 끝 ####


######## 파일다운로드 로직 끝. ########


#### 페이지가 없는 경우(Not Found) 대응로직 시작 ####
@app.errorhandler(404)
def no_page_404_handler(error):
	#print(request.url)
	return no_page_404_xml("no_page_404_handler " + str(request.url) )

def no_page_404_xml(path):
	# NonValid Access Log추가 필요(path 이용, TODO)
	print(path)
	xmlres = make_response( render_template("Deny.xml"), 403 )
	xmlres = make_xml404_header( xmlres )
	return xmlres

def make_xml404_header(xml_response):
	xml_response.headers['Alt-Svc'] = 'h3=":443"; ma=86400'
	xml_response.headers['Cache-Control'] = 'private, max-age=0'
	xml_response.headers['Cf-Cache-Status'] = 'MISS'
	xml_response.headers['Cf-Ray'] = '0000000000000000-ICN'
	#xmlres.headers['Content-Encoding'] = 'br'
	xml_response.headers['Content-Type'] = 'application/xml; charset=UTF-8'
	xml_response.headers['Cross-Origin-Opener-Policy-Report-Only'] = 'same-origin; report-to="gfe-default_product_name"'
	#xmlres.headers['Date'] = 'Fri, 06 Oct 2023 01:11:17 GMT'
	#xmlres.headers['Expires'] = 'Fri, 06 Oct 2023 01:11:17 GMT'
	xml_response.headers['Report-To'] = '{"group":"gfe-default_product_name","max_age":2592000,"endpoints":[{"url":"https://imholic.com/"}]}'
	#xmlres.headers['server'] = 'cloudflare'
	xml_response.headers['IMH-Server-Info'] = 'IMH/ISG One Common Central Cloud Core Computing Center (IO6C Center)'
	xml_response.headers['Vary'] = 'Accept-Encoding'
	#xmlres.headers['X-Guploader-Uploadid'] = 'ADPycduNzSD1phXxnjXTk4jLEKOkJ9mBBq5Q_R4CQr2CoXdXILedKaunzWHxSW1DJrgT0SW3GospfScFBlcyKvHHfnl_fw'
	xml_response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive, nocache, noimageindex, noodp'
	return xml_response
#### 페이지가 없는 경우(Not Found) 대응로직 끝 ####

def ajax_response(status, msg):
	status_code = "ok" if status else "error"
	return json.dumps(dict(
		status=status_code,
		msg=msg,
	))
