package 'python-pip'
package 'build-essential'
include_recipe "repository"
require 'socket'

hostname = Socket.gethostbyname(Socket.gethostname).first
repo_dir = File.realpath(File.join(File.dirname(__FILE__), '..', '..', '..'))
name = node[:user]

ga_client_id = ENV['GA_CLIENT_ID']
ga_client_secret = ENV['GA_CLIENT_SECRET']
authorization_csv_url = ENV['AUTH_CSV_URL']
ga_redirect_uri = "http://#{hostname}/callback"

#
# Put code where it needs to be.
#
execute "pip install -r requirements.txt" do
  cwd repo_dir
end

execute 'pip install honcho[export]'

execute "pip install -U ." do
  cwd repo_dir
end

#
# Populate working directories.
#
directory "/var/opt/bizarro-work" do
  action :delete
  recursive true
end

directory "/var/opt/bizarro-work" do
  owner name
  group name
  mode "0775"
end

#
# Ensure upstart job exists.
#
env_file = '/etc/ceviche.conf'

file env_file do
  content <<-CONF
RUNNING_STATE_DIR=/var/run/#{name}
REPO_PATH=/var/opt/bizarro-site
WORK_PATH=/var/opt/bizarro-work
BROWSERID_URL=#{hostname}

GA_CLIENT_ID="#{ga_client_id}"
GA_CLIENT_SECRET="#{ga_client_secret}"
GA_REDIRECT_URI="#{ga_redirect_uri}"
CONF
end

execute "honcho export upstart /etc/init" do
  command "honcho -e #{env_file} export -u #{name} -a bizarro-cms upstart /etc/init"
  cwd repo_dir
end

#
# Make it go.
#
execute "stop bizarro-cms" do
  returns [0, 1]
end

execute "start bizarro-cms"
