import os
import sys
import uuid
from flask import Flask, Response, request, send_file, session, jsonify, redirect, abort, make_response, render_template
import requests
import Login
import Job
import Register
import Account
import Admin
import Database

app = Flask(__name__, static_url_path='/static', static_folder="static")
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# request.headers["Cache-Control"] = "no-cache, no-store, must-revalidate" # HTTP 1.1.
# request.headers["Pragma"] = "no-cache" # HTTP 1.0.
# request.headers["Expires"] = "0" # Proxies.

@app.after_request
def after_request(response):
	response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
	response.headers["Expires"] = '0'
	response.headers["Pragma"] = "no-cache"
	return response

@app.route('/create', methods=['GET'])
def create_job():
	return render_template("index.html")

@app.route('/create_job', methods=['POST'])
def handle_form():

	def addDefaultParameters(parameters):
		default_parameters = {
			"sim_type":"MD",
			"max_density_multiplier":10,
			"verlet_skin":0.5,
			"time_scale":"linear",
			"ensemble":"NVT",
			"thermostat":"john",
			"diff_coeff":2.5,
			"backend_precision":"double",
			"lastconf_file":"last_conf.dat",
			"trajectory_file":"trajectory.dat",
			"energy_file":"energy.dat",
			"refresh_vel":1,
			"restart_step_counter":1,
			"newtonian_steps": 103
		}
	
		for (key, value) in default_parameters.items():
			if key not in parameters:
				parameters[key] = default_parameters[key]

	#if session.get("user_id") is None:
	#	return "You must be logged in to submit a job!"

	user_id = session["user_id"]
	if type(user_id) == str:
		try:
			user_id = int(user_id.strip('"'))
		except ValueError:
			return "Submission error"
			
	activeJobCount = Admin.getUserActiveJobCount(user_id)
	jobLimit = Admin.getJobLimit(user_id)

	if (activeJobCount >= jobLimit):
		return "You have reached the maximum number of running jobs."

	if (Admin.getTimeLimit(user_id) <= 0):
		return "You have reached the monthly time limit for running jobs."

	json_data = request.get_json()

	parameters = {}

	for (file_name, _) in json_data["files"].items():
		if(".top" in file_name):
			parameters.update({"topology": file_name})
		if(".dat" in file_name or ".conf" in file_name or ".oxdna" in file_name):
			parameters.update({"conf_file": file_name})

	parameters.update(json_data["parameters"])
	files = json_data["files"]

	if "force_file" in json_data:
		force_file_name = json_data["parameters"]["external_forces_file"]
		files[force_file_name] = json_data["force_file"]


	addDefaultParameters(parameters)

	metadata = {}

	job_data = {
		"metadata":metadata,
		"parameters": parameters, 
		"files": files
	}
	job_id = str(uuid.uuid4())
	success, error_message = Job.createJobForUserIdWithData(user_id, job_data, job_id)

	if success:
		return "Success" + job_id
	else:
		return error_message

@app.route("/guestcreate", methods=["GET"])
def create_guest_job():
	return render_template("guestcreate.html")

@app.route('/cancel_job', methods=['POST'])
def cancel_job():
	print("Received Cancel Request")
	if session.get("user_id") is None:
		return "You must be logged in to cancel this job!"

	json_data = request.get_json()
	jobId = json_data["jobId"]
	print("Canceling Job " + jobId)
	Job.cancelJob(jobId)
	return "Canceled Job " + jobId

@app.route('/delete_job', methods=['POST'])
def delete_job():
	print("Received Delete Request")
	if session.get("user_id") is None:
		return "You must be logged in to delete this job!"

	json_data = request.get_json()
	job_uuid = json_data["jobId"]
	print("Deleting Job " + job_uuid)
	Job.deleteJob(job_uuid)
	return "Deleted Job " + job_uuid

@app.route('/job_status/<jobId>', methods=['GET'])
def job_status(jobId):
	status = Job.getJobStatus(jobId)
	return status


@app.route('/api/create_analysis', methods=["POST"])#<jobId>/<analysis_type>', methods=['POST'])
def create_analysis():#jobId, analysis_type):

	if session.get("user_id") is None:
		return "You must be logged in to submit a job!"

	json_data = request.get_json()
	from sys import stderr

	userId = session["user_id"]

	return Job.createAnalysisForUserIdWithJob(userId, json_data)

	#return "Analysis created!"
@app.route("/verify", methods = ["GET"])
def verify():
	#TODO refactor to use exceptions
	if (request.method == "GET"):
		#Two files to choose from based on html query strings
		#Success
		#Failure
		#Expecting two query strings, user id, and autogenerated verification code
		if (request.args):
			#get query strings
			args = request.args
			userId = args.get("id")
			code = args.get("verify")
			#check if query strings are present
			if (userId and code):
				#verify the user
				if(Account.verifyUser(userId, code)):
					return send_file("templates/verify/success.html")
				else:
					return send_file("templates/verify/fail.html")
			else:
				return send_file("templates/verify/fail.html")
		else:
			return send_file("templates/verify/fail.html")

@app.route("/register", methods=["GET", "POST"])
def register():
	print("NOW REGISTERING USER!")

	if request.method == "GET":
		return render_template("register.html")

	if request.method == "POST":
		user = request.get_json()
		return Register.registerUser(user)

@app.route("/getcookie", methods=["POST"])
def get_cookie():
	cookie = request.cookies.get('guest_id')
	return cookie if cookie else "-1"

@app.route("/setcookie", methods=["POST"])
def set_cookie():
	id = request.data.decode("utf-8")
	resp = make_response()
	resp.set_cookie('guest_id', id)
	return resp

@app.route("/setsessionid", methods=["POST"])
def set_session_id():
	session["user_id"] = request.data.decode("utf-8")
	session["name"] = Account.getFirstName(session[user_id])
	return "Success"

@app.route("/getsessionid", methods=["POST"])
def get_session_id():
	return session["user_id"] if session["user_id"] else "None"

@app.route("/registerguest", methods=["POST"])
def register_guest():
	print("NOW REGISTERING GUEST USER!")
	if request.method == "POST":
		response = Register.registerGuest()
		session["user_id"] = response
		session["name"] = Account.getFirstName()
		return response

@app.route("/login", methods=["GET", "POST"])
def login():

	if request.method == "GET":
		return render_template("login.html")

	if request.method == "POST":
		username = request.form["username"]
		password = request.form["password"]
	if username is not None and password is not None:
		user_id = Login.loginUser(username, password)
		if(user_id > -1):
			session["user_id"] = user_id
			session["name"] = Account.getFirstName(user_id)
			return redirect("/")
		elif(user_id == -2):
			return "Error, user not verified. Please verify using the link sent to the email you registered with."
		else:
			return "Invalid username or password"
		
	return "Invalid username or password"

@app.route("/logout")
def logout():
	session["user_id"] = None
	session["name"] = None
	return redirect("/")


@app.route("/account", methods=["GET"])
def account():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	if request.method == "GET":
		return render_template("account.html")

@app.route("/password/forgot", methods=["GET"])
def forgotPassword():
	if session.get("user_id"):
		return "You must be logged out"

	if request.method == "GET":
		return send_file("templates/password/forgot.html")

@app.route("/password/forgot/send_reset_token", methods=["POST"])
def sendResetToken():
	username = request.json["email"]
	return Account.sendResetToken(username)

@app.route("/password/reset", methods=["GET", "POST"])
def resetPassword():
	if request.method == "GET":
		token = request.args.get('token')
		userId = Account.checkToken(token)
		if userId == 0:
			return "Invalid URL"
		elif userId == -1:
			return "Reset token expired: please try again"
		else:
			return send_file("templates/password/reset.html")
	
	if request.method == "POST":
		token = request.json["token"]
		userId = Account.checkToken(token)
		if userId == 0:
			return "Invalid URL"
		elif userId == -1:
			return "Reset token expired: please try again"
		else:
			newPassword = request.json["newPassword"]
			if len(newPassword) < 8:
				return "Password must be at least 8 characters"
			return Account.resetPassword(userId, newPassword)

@app.route("/account/update_password", methods=["POST"])
def updatePassword():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])

	old_password = request.json["old_password"]
	new_password = request.json["new_password"]

	if len(new_password) < 8:
		return "Password must be at least 8 characters"
	if new_password == old_password:
		return "Choose a different password"

	return Login.updatePasssword(user_id, old_password, new_password)

@app.route("/account/get_email_prefs", methods=["GET"])
def getEmailPrefs():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])
	
	return Account.getEmailPrefs(user_id)

@app.route("/account/set_email_prefs/<prefs>", methods=["GET"])
def setEmailPrefs(prefs):
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])
	
	return Account.setEmailPrefs(user_id, prefs)

@app.route("/account/get_email", methods=["GET"])
def getEmail():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])
	
	return Account.getEmail(user_id)

@app.route("/account/set_email", methods=["POST"])
def updateEmail():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])
	email_new = string(session["email"])
	
	return Account.setEmail(user_id, email_new)

@app.route("/account/get_status", methods=["GET"])
def getStatus():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])
	
	return Account.getStatus(user_id)

@app.route("/account/get_creation_date", methods=["GET"])
def getCreationDate():
	if session.get("user_id") is None:
		return "You must be logged in to modify your account"

	user_id = int(session["user_id"])
	
	return Account.get_creation_date(user_id)

@app.route("/jobs")
def jobs():

	if session.get("user_id") is None:
		return redirect("/login")
	else:
		return render_template("jobs.html")

@app.route("/guestjob/<job_id>")
def view_guest_job(job_id):
	session["user_id"] = Job.getUserIdForJob(job_id)
	session["name"] = Account.getFirstName(user_id)
	return render_template("guestjob.html")

@app.route("/job/<job_id>")
def view_job(job_id):

	if session.get("user_id") is None:
		return redirect("/login")
	else:
		return render_template("job.html")

@app.route("/job/update_name/<name>/<uuid>")
def update_job_name(name, uuid):
	user_id = session.get("user_id")
	if user_id is None:
		return redirect("/login")
	
	return Job.updateJobName(name, uuid)

@app.route("/api/job/<job_id>")
def get_job_data(job_id):

	if session.get("user_id") is None:
		return redirect("/login")

	job_data = Job.getJobForUserId(job_id, session.get("user_id"))
	associated_jobs = Job.getAssociatedJobs(job_data["uuid"])

	if(job_data is not None):
		return jsonify({
			"job_data" : [job_data],
			"associated_jobs" : associated_jobs
		})
	else:
		return "No job data."

@app.route("/api/job/isRelax/<job_id>")
def get_is_relax(job_id):
	if session.get("user_id") is None:
		return redirect("/login")

	return Job.isRelax(job_id)

@app.route("/api/job/hasTrajectory/<job_id>")
def has_trajectory(job_id):
	if session.get("user_id") is None:
		return redirect("/login")

	return Job.hasTrajectory(job_id)

@app.route("/api/jobs_status/<job_id>")
def get_status(job_id):
	if session.get("user_id") is None:
		return redirect("/login")
	
	return Job.getJobStatus(job_id)

@app.route("/api/job")
def getQueue():
	return Job.getQueue()

@app.route("/all_jobs")
def getJobs():

	if session.get("user_id") is None:
		return "You must be logged in to view your jobs"

	user_id = int(session["user_id"])

	jobs = Job.getJobsForUserId(user_id)

	return jsonify(jobs)

@app.route("/analysis_output/<uuid>/<analysis_id>/<desired_output>") 
def getAnalysisOutput(uuid, analysis_id, desired_output):
	if session.get("user_id") is None:
		return "You must be logged in to view the output of a job"

	user_directory = "/users/" + str(session["user_id"]) + "/"
	job_directory =  user_directory + uuid + "/"

	desired_output_map = {
		"distance_data" : ".txt",
		"distance_hist" : "_hist.png",
		"distance_traj" : "_traj.png",
		"distance_log" :  ".log",
		"angle_plot_data" : ".txt",
		"angle_plot_hist" : "_hist.png",
		"angle_plot_traj" : "_traj.png",
		"angle_plot_log" : ".log",
		"energy_log" : ".log",
		"energy_hist" : "_hist.png",
		"energy_traj" : "_traj.png"
	}

	desired_file_path = ""
	job_data = Job.getAssociatedJobs(uuid)
	if job_data:
		for job in job_data:
			if job["uuid"] == analysis_id:
				desired_file_path = job_directory + job["name"] + desired_output_map[desired_output]
		if not desired_file_path:
			print("No output found for query {}".format)

	if "log" in desired_output_map:
		try:
			desired_file = open(desired_file_path, "r")
			desired_file_contents = desired_file.read()
			return Response(desired_file_contents, mimetype='text/plain')
		except:
			abort(404, description="{type} for job {uuid} is currently unfinished".format(type=desired_output, uuid=analysis_id))
	else:
		try:
			return send_file(desired_file_path, as_attachment=True)
		except:
			abort(404, description="{type} for job {uuid} is currently unfinished".format(type=desired_output, uuid=analysis_id))

@app.route("/job_output/<uuid>/<desired_output>")
def getJobOutput(uuid, desired_output):

	if session.get("user_id") is None:
		return "You must be logged in to view the output of a job"


	desired_output_map = {
		"energy":"energy.dat",
		"trajectory_zip":"trajectory.zip",
		"trajectory_txt":"trajectory.dat",
        "topology": "output.top",
		"init_conf": "output.dat",
		"init_conf_relax": "MD_relax.dat",
		"last_conf": "last_conf.dat",
		"log":"job_out.log",
		"mean_log":"mean.log",
		"align_log":"align.log",
		"analysis_log":"analysis_out.log",
		"input":"input",
		"mean":"mean.dat",
		"deviations":"deviations.json",
		"aligned_traj":"aligned.zip",
		"bond_log":"bond.log",
		"bond_output":"bond_occupancy.json",
		"angle_find_log":"angle_find.log",
		"angle_find_output":"duplex_angle.txt"
	}

	if desired_output not in desired_output_map:
		return "You must specify a valid desired output"
	

	user_directory = "/users/" + str(session["user_id"]) + "/"
	job_directory =  user_directory + uuid + "/"
	desired_file_path = job_directory + desired_output_map[desired_output]

	if not "traj" in desired_output and not "zip" in desired_output:
		try:
			desired_file = open(desired_file_path, "r")
			desired_file_contents = desired_file.read()
			desired_file.close()
			return Response(desired_file_contents, mimetype='text/plain')
		except:
			abort(404, description="No {type} found for job {uuid}\nEither the job hasn't produced that output yet or something has gone horribly wrong".format(type=desired_output, uuid=uuid))

	#trajectories and zipfiles are presumably too big to serve as text
	else:
		if os.path.isfile(desired_file_path):
			return send_file(desired_file_path, as_attachment=True)

		#backwards compatibility for both compressed and uncompressed filess
		elif "trajectory" in desired_output:
			desired_file_path = job_directory + desired_output_map["trajectory_txt"]
			try:
				a = open(desired_file_path, "r")
				a.close()
				return send_file(desired_file_path, as_attachment=True)
			
			except:
				abort(404, description="No {type} found for job {uuid}\nEither the job hasn't produced that output yet or something has gone horribly wrong".format(type=desired_output, uuid=uuid))
		else:
			abort(404, description="No {type} found for job {uuid}\nEither the job hasn't produced that output yet or something has gone horribly wrong".format(type=desired_output, uuid=uuid))



@app.route("/admin")
def admin():
	userID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(userID)
	if isAdmin == 1:
		return render_template("admin.html")
	else:
		return "You must be an admin to access this page."

@app.route("/admin/recentlyaddedusers")
def recentlyAddedUsers():
	newUsers = Admin.getRecentlyAddedUsers()
	users = tuple(newUsers)
	return jsonify(users)

@app.route("/admin/all_users")
def allUsers():
	allUsers = Admin.getAllUsers()
	users = tuple(allUsers)
	return jsonify(users)

@app.route("/admin/promoteToAdmin/<username>")
def promoteToAdmin(username):
	loggedInUserID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(loggedInUserID)
	if isAdmin == 1:
		userID = Admin.getID(username)
		Admin.promoteToAdmin(userID)
		return username + " promoted to Admin"

@app.route("/admin/promoteToPrivaleged/<username>")
def promoteToPrivaleged(username):
	loggedInUserID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(loggedInUserID)
	if isAdmin == 1:
		userID = Admin.getID(username)
		Admin.promoteToPrivaleged(userID)
		return username + " promoted to privaleged"

@app.route("/admin/getJobLimit/<username>")
def getJobLimit(username):
	loggedInUserID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(loggedInUserID)
	if isAdmin == 1:
		userID = Admin.getID(username)
		return Admin.getJobLimit(userID)

@app.route("/admin/setJobLimit/<username>/<jobLimit>")
def setJobLimit(username, jobLimit):
	loggedInUserID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(loggedInUserID)
	if isAdmin == 1:
		try:
			jobLimitInt = int(jobLimit)
		except ValueError:
			return "Failure: enter an integer value"
		if jobLimitInt > 127 or jobLimitInt < -127:
			return "Failure: maximum value is 127"
		userID = Admin.getID(username)
		Admin.setJobLimit(userID, jobLimit)
		return username + "'s job limit set to " + jobLimit

@app.route("/admin/setTimeLimit/<username>/<timeLimit>")
def setTimeLimit(username, timeLimit):
	loggedInUserID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(loggedInUserID)
	if isAdmin == 1:
		try:
			timeLimitInt = int(timeLimit)
		except ValueError:
			return "Failure: enter an integer value"
		userID = Admin.getID(username)
		Admin.setTimeLimit(userID, timeLimit)
		return username + "'s time limit set to " + str(timeLimitInt / 3600) + " hours"

@app.route("/admin/deleteUser/<user_id>")
def deleteUser(user_id):
	loggedInUserID = session.get("user_id")
	isAdmin = Admin.checkIfAdmin(loggedInUserID)
	
	if isAdmin == 1:
		return Admin.deleteUser(user_id)

@app.route("/admin/getUserID/<username>")
def getUserID(username):
	userID = Admin.getID(username)
	return jsonify(userID)


@app.route("/admin/getUserInfo/<username>")
def getUserInfo(username):
	userID = Admin.getID(username)
	#jobCount = Admin.getUserJobCount(uuid)
	isAdmin = Admin.checkIfAdmin(userID)
	if isAdmin == 1:
		isAdmin = "True"
	else:
		isAdmin = "False"
	isPrivaleged = Admin.checkIfPrivaleged(userID)
	if isPrivaleged == 1:
		isPrivaleged = "True"
	else:
		isPrivaleged = "False"
	jobLimit = Admin.getJobLimit(userID)
	timeLimit = Admin.getTimeLimit(userID)
	jobCount = Admin.getUserJobCount(userID)
	info = (jobCount, jobLimit, timeLimit, isAdmin, isPrivaleged, userID)
	return jsonify(info)

@app.route("/images/<image>")
def getImage(image=None):
	if os.path.isfile("images/{}".format(image)):
		return send_file("images/{}".format(image))
	else:
		abort(404, discription="Image not found")

@app.route("/")
def index():
	return render_template("landing.html")

if __name__ == '__main__':
	app.run(host="0.0.0.0", port=9000)
