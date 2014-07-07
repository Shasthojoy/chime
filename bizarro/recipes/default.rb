include_recipe "python"
package "git"

git "/opt/bizarro-cms" do
  repository node['repo']
  reference node['ref']
end

execute "pip install -r requirements.txt" do
  cwd "/opt/bizarro-cms"
end

group node[:user]
user node[:user] do
  gid node[:user]
end

directory "/var/opt/bizarro-work" do
  owner node[:user]
  group node[:user]
  mode "0775"
end

directory "/var/opt/sample-site" do
  owner node[:user]
  group node[:user]
  mode "0775"
end

bash "tar -xzf sample-site.tar.gz" do
  code "tar -C /var/opt -xzf /opt/bizarro-cms/sample-site.tar.gz"
  user node[:user]
  creates "/var/opt/sample-site/config"
end

env_file = File.realpath(File.join(File.dirname(__FILE__), 'honcho-env'))

execute "honcho export upstart /etc/init" do
  command "honcho -e #{env_file} export -u #{node[:user]} -a bizarro-cms upstart /etc/init"
  cwd "/opt/bizarro-cms"
end

execute "stop bizarro-cms" do
  returns [0, 1]
end

execute "start bizarro-cms"
