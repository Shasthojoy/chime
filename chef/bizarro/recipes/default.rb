package 'python-pip'
package 'build-essential'
include_recipe "repository"

repo_dir = File.realpath(File.join(File.dirname(__FILE__), '..', '..', '..'))
name = node[:user]

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
env_file = File.realpath(File.join(File.dirname(__FILE__), 'honcho-env'))

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
