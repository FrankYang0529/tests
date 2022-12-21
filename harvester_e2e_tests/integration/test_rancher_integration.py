# Copyright (c) 2021 SUSE LLC
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of version 3 of the GNU General Public License as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.   See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, contact SUSE LLC.
#
# To contact SUSE about this file by physical or electronic mail,
# you may find current contact information at www.suse.com

import base64
from time import sleep
from datetime import datetime, timedelta

import pytest

from rancher_api import DEFAULT_NAMESPACE, FLEET_DEFAULT_NAMESPACE


pytest_plugins = [
    'harvester_e2e_tests.fixtures.api_client',
    'harvester_e2e_tests.fixtures.rancher_api_client',
]


@pytest.mark.p0
@pytest.mark.rke2
@pytest.mark.rancher
class TestRKE2:
    def test_create_mgmt_cluster(self, rancher_api_client, unique_name, wait_timeout):
        code, data = rancher_api_client.mgmt_clusters.create(
            self.get_harvester_cluster_name(unique_name),
            labels={
                "provider.cattle.io": "harvester"
            }
        )

        assert 201 == code, (
            f"Failed to create MgmtCluster {self.get_harvester_cluster_name(unique_name)} with \
                error: {code}, {data}"
        )

        endtime = datetime.now() + timedelta(seconds=wait_timeout)
        while endtime > datetime.now():
            code, data = rancher_api_client.mgmt_clusters.get(
                self.get_harvester_cluster_name(unique_name))
            if 'status' in data and 'clusterName' in data['status']:
                break
            sleep(5)
        else:
            raise AssertionError(
                f"Can't find clusterName in MgmtCluster \
                    {self.get_harvester_cluster_name(unique_name)} with {wait_timeout} timed out\n"
                f"Got error: {code}, {data}"
            )

    def test_import_harvester_to_rancher(self, api_client, rancher_api_client, unique_name,
                                         wait_timeout):
        code, data = rancher_api_client.mgmt_clusters.get(
            self.get_harvester_cluster_name(unique_name)
        )
        clusterName = data['status']['clusterName']
        endtime = datetime.now() + timedelta(seconds=wait_timeout)
        while endtime > datetime.now():
            code, data = rancher_api_client.cluster_registration_tokens.get(clusterName)
            if code == 200 and 'manifestUrl' in data:
                break
            sleep(5)
        else:
            raise AssertionError(
                f"Can't find clusterRegistrationToken for cluster {clusterName} \
                    with {wait_timeout} timed out\n"
                f"Got error: {code}, {data}"
            )

        manifestUrl = data['manifestUrl']
        updates = {
            "value": manifestUrl
        }
        code, data = api_client.settings.update("cluster-registration-url", updates)
        assert 200 == code, (
            f"Failed to update cluster-registration-url setting with error: {code}, {data}"
        )

        endtime = datetime.now() + timedelta(seconds=wait_timeout)
        while endtime > datetime.now():
            code, data = rancher_api_client.mgmt_clusters.get(
                self.get_harvester_cluster_name(unique_name)
            )
            if 'status' in data and 'ready' in data['status'] and data['status']['ready']:
                break
            sleep(5)
        else:
            raise AssertionError(
                f"MgmtCluster {self.get_harvester_cluster_name(unique_name)} can't be ready \
                    with {wait_timeout} timed out\n"
                f"Got error: {code}, {data}"
            )

    def test_cloud_credential(self, api_client, rancher_api_client, unique_name):
        _, data = rancher_api_client.mgmt_clusters.get(
            self.get_harvester_cluster_name(unique_name)
        )
        harvester_kubeconfig = api_client.generate_kubeconfig()
        code, data = rancher_api_client.cloud_credentials.create(
            unique_name,
            data['status']['clusterName'],
            harvester_kubeconfig
        )

        assert 201 == code, (
            f"Failed to create cloud credential with error: {code}, {data}"
        )

    def test_create_vlan(self, api_client, unique_name):
        code, data = api_client.networks.create(unique_name, 1)

        assert 201 == code, (
            f"Failed to create vlan network with error: {code}, {data}"
        )

    def test_upload_image(self, api_client, unique_name, wait_timeout):
        code, data = api_client.images.create_by_url(
            unique_name,
            'http://cloud-images.ubuntu.com/releases/focal/release/ubuntu-20.04-server-cloudimg-amd64-disk-kvm.img'  # noqa
        )

        assert 201 == code, (
            f"Failed to upload focal image with error: {code}, {data}"
        )

        endtime = datetime.now() + timedelta(seconds=wait_timeout)
        while endtime > datetime.now():
            code, data = api_client.images.get(unique_name)
            if 'status' in data and 'progress' in data['status'] and \
                    data['status']['progress'] == 100:
                break
            sleep(5)
        else:
            raise AssertionError(
                f"Image {unique_name} can't be ready with {wait_timeout} timed out\n"
                f"Got error: {code}, {data}"
            )

    def test_create_rke2(self, api_client, rancher_api_client, unique_name, k8s_version):
        code, data = rancher_api_client.mgmt_clusters.get(
            self.get_harvester_cluster_name(unique_name)
        )
        clusterName = data['status']['clusterName']
        resp = rancher_api_client.kube_configs.create(
            self.get_rke2_cluster_name(unique_name),
            clusterName
        )
        assert 200 == resp.status_code, (
            f"Failed to create harvester kubeconfig for rke2 with error: \
                {resp.status_code}, {resp.text}"
        )

        kubeconfig = resp.text.replace("\\n", "\n")[1:-1]

        code, data = rancher_api_client.secrets.create(
            name=unique_name,
            namespace=FLEET_DEFAULT_NAMESPACE,
            data={
                "credential": base64.b64encode(kubeconfig.encode('UTF-8')).decode('UTF-8')
            },
            annotations={
                "v2prov-secret-authorized-for-cluster": self.get_rke2_cluster_name(unique_name),
                "v2prov-authorized-secret-deletes-on-cluster-removal": "true"
            }
        )

        assert 201 == code, (
            f"Failed to create secret with error: {code}, {data}"
        )

        code, data = rancher_api_client.harvester_configs.create(
            name=unique_name,
            cpu_count="2",
            disk_size="40",
            memory_size="4",
            image_name=f"{DEFAULT_NAMESPACE}/{unique_name}",
            network_name=unique_name,
            user_data=base64.b64encode("""
#cloud-config
password: test
chpasswd:
    expire: false
ssh_pwauth: true
            """.encode('UTF-8')).decode('UTF-8')
        )

        assert 201 == code, (
            f"Failed to create harvester config with error: {code}, {data}"
        )

        code, data = rancher_api_client.cloud_credentials.list()
        cloud_credential = None
        for d in data['data']:
            if d['name'] == unique_name:
                cloud_credential = d
                break

        assert cloud_credential is not None, (
            f"Failed to find cloud credential: {data}"
        )

        code, data = rancher_api_client.mgmt_clusters.create(
            self.get_rke2_cluster_name(unique_name),
            spec={
                "rkeConfig": {
                    "chartValues": {
                        "rke2-calico": {},
                        "harvester-cloud-provider": {
                            "clusterName": self.get_rke2_cluster_name(unique_name),
                            "cloudConfigPath": "/var/lib/rancher/rke2/etc/config-files/cloud-provider-config"  # noqa
                        }
                    },
                    "upgradeStrategy": {
                        "controlPlaneConcurrency": "1",
                        "controlPlaneDrainOptions": {
                            "deleteEmptyDirData": True,
                            "disableEviction": False,
                            "enabled": False,
                            "force": False,
                            "gracePeriod": -1,
                            "ignoreDaemonSets": True,
                            "ignoreErrors": False,
                            "skipWaitForDeleteTimeoutSeconds": 0,
                            "timeout": 120
                        },
                        "workerConcurrency": "1",
                        "workerDrainOptions": {
                            "deleteEmptyDirData": True,
                            "disableEviction": False,
                            "enabled": False,
                            "force": False,
                            "gracePeriod": -1,
                            "ignoreDaemonSets": True,
                            "ignoreErrors": False,
                            "skipWaitForDeleteTimeoutSeconds": 0,
                            "timeout": 120
                        }
                    },
                    "machineGlobalConfig": {
                        "cni": "calico",
                        "disable-kube-proxy": False,
                        "etcd-expose-metrics": False,
                        "profile": None
                    },
                    "machineSelectorConfig": [
                        {
                            "config": {
                                "cloud-provider-config": f"secret://{FLEET_DEFAULT_NAMESPACE}:{unique_name}",  # noqa
                                "cloud-provider-name": "harvester",
                                "protect-kernel-defaults": False
                            }
                        }
                    ],
                    "etcd": {
                        "disableSnapshots": False,
                        "s3": None,
                        "snapshotRetention": 5,
                        "snapshotScheduleCron": "0 */5 * * *"
                    },
                    "registries": {
                        "configs": {},
                        "mirrors": {}
                    },
                    "machinePools": [
                        {
                            "name": "pool1",
                            "etcdRole": True,
                            "controlPlaneRole": True,
                            "workerRole": True,
                            "hostnamePrefix": f"{unique_name}-",
                            "labels": {},
                            "quantity": 1,
                            "unhealthyNodeTimeout": "0m",
                            "machineConfigRef": {
                                    "kind": "HarvesterConfig",
                                    "name": unique_name
                            }
                        }
                    ]
                },
                "machineSelectorConfig": [
                    {
                        "config": {}
                    }
                ],
                "kubernetesVersion": k8s_version,
                "defaultPodSecurityPolicyTemplateName": "",
                "cloudCredentialSecretName": cloud_credential['id'],
                "localClusterAuthEndpoint": {
                    "enabled": False,
                    "caCerts": "",
                    "fqdn": ""
                }
            }
        )

        assert 201 == code, (
            f"Failed to create RKE2 MgmtCluster {unique_name} with error: {code}, {data}"
        )

    def get_harvester_cluster_name(self, unique_name):
        return f"{unique_name}-harv"

    def get_rke2_cluster_name(self, unique_name):
        return f"{unique_name}-rke2"
