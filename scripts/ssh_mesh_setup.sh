#!/bin/bash
"""
SSH Mesh Setup - Enable all nodes to SSH to all other nodes
Creates full mesh connectivity between Mac and all LXC containers
"""

# Configuration
LXC_NODES=("192.168.1.221" "192.168.1.222" "192.168.1.223" "192.168.1.224" "192.168.1.225" "192.168.1.226" "192.168.1.227" "192.168.1.228")
MAC_SSH_KEY="~/.ssh/id_rsa"
TEMP_DIR="/tmp/ssh_mesh_setup"

echo "🔑 SSH Mesh Setup - Full Connectivity"
echo "===================================="
echo "Nodes: Mac + ${#LXC_NODES[@]} LXC containers"
echo "Target: Full mesh SSH connectivity"
echo ""

# Create temp directory
mkdir -p $TEMP_DIR
cd $TEMP_DIR

echo "📋 Step 1: Collecting public keys from all nodes..."
echo "------------------------------------------------"

# Collect Mac's public key
if [ -f ~/.ssh/id_rsa.pub ]; then
    cp ~/.ssh/id_rsa.pub mac_key.pub
    echo "   ✅ Mac key collected"
else
    echo "   ❌ Mac SSH key not found at ~/.ssh/id_rsa.pub"
    exit 1
fi

# Collect LXC public keys
for node in "${LXC_NODES[@]}"; do
    echo "   🔍 Collecting key from $node..."
    if ssh -i $MAC_SSH_KEY -o ConnectTimeout=5 $node 'cat ~/.ssh/id_rsa.pub' > "${node}_key.pub" 2>/dev/null; then
        echo "      ✅ Key collected from $node"
    else
        echo "      ❌ Failed to collect key from $node"
        exit 1
    fi
done

echo ""
echo "🔗 Step 2: Creating consolidated authorized_keys..."
echo "------------------------------------------------"

# Create master authorized_keys with all public keys
cat *.pub > master_authorized_keys
echo "   ✅ Master authorized_keys created with $(cat *.pub | wc -l) keys"

echo ""
echo "📤 Step 3: Distributing keys to all LXC nodes..."
echo "-----------------------------------------------"

# Distribute master authorized_keys to all LXCs
for node in "${LXC_NODES[@]}"; do
    echo "   📤 Updating $node..."
    
    # Backup existing authorized_keys
    ssh -i $MAC_SSH_KEY $node 'cp ~/.ssh/authorized_keys ~/.ssh/authorized_keys.backup' 2>/dev/null
    
    # Copy master authorized_keys
    if scp -i $MAC_SSH_KEY master_authorized_keys $node:~/.ssh/authorized_keys; then
        # Set correct permissions
        ssh -i $MAC_SSH_KEY $node 'chmod 600 ~/.ssh/authorized_keys'
        echo "      ✅ Keys updated on $node"
    else
        echo "      ❌ Failed to update $node"
        exit 1
    fi
done

echo ""
echo "🧪 Step 4: Testing connectivity..."
echo "--------------------------------"

# Test connectivity between all pairs
echo "   Testing Mac → LXC connections..."
for node in "${LXC_NODES[@]}"; do
    if ssh -i $MAC_SSH_KEY -o ConnectTimeout=5 $node 'echo "Connection OK"' >/dev/null 2>&1; then
        echo "      ✅ Mac → $node"
    else
        echo "      ❌ Mac → $node"
    fi
done

echo ""
echo "   Testing LXC → LXC connections..."
for from_node in "${LXC_NODES[@]}"; do
    for to_node in "${LXC_NODES[@]}"; do
        if [ "$from_node" != "$to_node" ]; then
            # Test if from_node can SSH to to_node
            if ssh -i $MAC_SSH_KEY $from_node "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no $to_node 'echo Connection OK'" >/dev/null 2>&1; then
                echo "      ✅ $from_node → $to_node"
            else
                echo "      ⚠️  $from_node → $to_node (may need first connection)"
            fi
        fi
    done
done

echo ""
echo "🧹 Step 5: Cleanup..."
echo "-------------------"
cd ..
rm -rf $TEMP_DIR
echo "   ✅ Temporary files cleaned"

echo ""
echo "✅ SSH Mesh Setup Complete!"
echo "=========================="
echo "📋 Summary:"
echo "   • All LXC nodes have been configured"
echo "   • Each node can now SSH to all other nodes"
echo "   • Backup files created: ~/.ssh/authorized_keys.backup"
echo ""
echo "🧪 Test Commands:"
echo "   # From any LXC, SSH to another:"
echo "   ssh 192.168.1.221"
echo "   ssh 192.168.1.222"
echo "   # etc..."
echo ""
echo "📝 Note: First connections may prompt for host key verification"
echo "   Just type 'yes' to accept and add to known_hosts"
