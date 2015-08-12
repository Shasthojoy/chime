Jekyll Install
=============

This is our installation of jekyll, which we use to preview and render
pages. Eventually this should happen automatically, but for now there's
a manual process to get it set up for development. This assumes rbenv
for managing ruby versions, but if you already have rvm, go ahead and
keep using that. (You can't use both; they conflict.)

It goes something like this:

* Install rbenv
  + Ubuntu: `apt-get install rbenv`
  + MacOS: `brew install rbenv ruby-build` or `brew upgrade rbenv ruby-build` (using [Homebrew](http://brew.sh/))
* activate rbenv temporarily or permanently
  + temporary: `eval "$(rbenv init -)"`
  + permanent: `echo 'eval "$(rbenv init -)"' >> ~/.bash_profile` (restart shell after)
* Install rvm-download
  + `git clone https://github.com/garnieretienne/rvm-download.git ~/.rbenv/plugins/rvm-download`
* Install and use the right ruby
  + `rbenv download 2.2.0`
  + `rbenv shell 2.2.0`
* Install bundler
  + `gem install bundler`
  + `rbenv rehash`
* Install the gems (using the *Gemfile* in the *jekyll/* directory)
  + `cd jekyll`
  + `bundle install`
  + `rbenv rehash`
* Check jekyll
  + `cd ..`
  + `jekyll/run-jekyll.sh --help`
  + Should produce the jekyll help, not error messages



