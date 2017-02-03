# -*- mode: ruby -*-
# vi: set ft=ruby :

def guess_public_key
  %w(ecdsa rsa dsa).each do |method|
    path = File.expand_path "~/.ssh/id_#{method}.pub"
    return IO.read path if File.exist? path
  end
  fail 'Public key not found.'
end

Vagrant.configure(2) do |config|
  config.vm.synced_folder ".", "/vagrant", disabled: true

  config.hostmanager.enabled = true
  config.hostmanager.manage_host = true
  config.hostmanager.ignore_private_ip = false
  config.hostmanager.include_offline = true

  config.vm.hostname = 'example.com'
  config.vm.box = 'debian/jessie64'

  config.vm.provider "virtualbox" do |v, override|
    override.vm.network :private_network, ip: "192.168.33.22"
    v.memory = 2048
    v.cpus = 2
    v.name = 'nuka'
  end

  config.vm.provision :shell, inline: <<SCRIPT
mkdir -p /root/.ssh
echo \"#{guess_public_key}\" >> /root/.ssh/authorized_keys
cat ~vagrant/.ssh/authorized_keys >> /root/.ssh/authorized_keys
apt-get install -y python-virtualenv wget perl-modules adduser
SCRIPT

end
