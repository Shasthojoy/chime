package 'apache2'

#
# Activate minimum required modules.
#
execute 'a2enmod mime'
execute 'a2enmod proxy'
execute 'a2enmod proxy_http'
execute 'a2enmod headers'
execute 'a2enmod include'
execute 'a2enmod authz_host'
# execute 'a2enmod log_config'
execute 'a2enmod vhost_alias'

# #
# # Create server configuration.
# #
# file "/etc/apache2/apache2.conf" do
#     owner "root"
#     group "root"
#     mode  "0644"
#     content File.open(File.dirname(__FILE__) + "/apache2.conf").read()
# end
# 
# file "/etc/apache2/bizarro-cms-vhost.conf" do
#     owner "root"
#     group "root"
#     mode  "0644"
#     content File.open(File.dirname(__FILE__) + "/bizarro-cms-vhost.conf").read()
# end
# 
# directory "/etc/apache2/sites-enabled" do
#   action    :delete
#   recursive true
# end

#
# Make it go.
#
execute "apache2ctl graceful" do
  path ['/usr/bin', '/usr/sbin', '/usr/local/bin', '/usr/local/sbin']
end
