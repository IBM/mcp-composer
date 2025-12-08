import{_ as l,C as r,c as i,o as n,a2 as a,b as t,w as e,a as o,G as c,a3 as u}from"./chunks/framework.HReQJDEI.js";const q=JSON.parse('{"title":"📘 Design Document: Versioned Configuration System","description":"","frontmatter":{},"headers":[],"relativePath":"config_manager_dd.md","filePath":"config_manager_dd.md"}'),d={name:"config_manager_dd.md"};function b(m,s,g,_,f,h){const p=r("Mermaid");return n(),i("div",null,[s[1]||(s[1]=a('<h1 id="📘-design-document-versioned-configuration-system" tabindex="-1">📘 Design Document: Versioned Configuration System <a class="header-anchor" href="#📘-design-document-versioned-configuration-system" aria-label="Permalink to &quot;📘 Design Document: Versioned Configuration System&quot;">​</a></h1><h2 id="objective" tabindex="-1">Objective <a class="header-anchor" href="#objective" aria-label="Permalink to &quot;Objective&quot;">​</a></h2><p>To implement a modular and secure version-controlled configuration system for managing configuration snapshots of server endpoints (e.g., OpenAPI, GraphQL) using adapters such as file storage for development and Vault for production.</p><hr><h2 id="architecture-overview" tabindex="-1">Architecture Overview <a class="header-anchor" href="#architecture-overview" aria-label="Permalink to &quot;Architecture Overview&quot;">​</a></h2>',5)),(n(),t(u,null,{default:e(()=>[c(p,{id:"mermaid-13",class:"mermaid-block",graph:"flowchart%20TD%0A%20%20%20%20subgraph%20Client%0A%20%20%20%20%20%20%20%20A%5BDeveloper%20or%20Service%5D%20--%3E%7Csave%2Fget%2Frollback%7C%20B%5BConfigManager%5D%0A%20%20%20%20end%0A%0A%20%20%20%20B%20--%3E%7CDelegates%7C%20C%7BSecretAdapter%20Interface%7D%0A%0A%20%20%20%20C%20--%3E%20D1%5BFileSecretAdapter%5D%0A%20%20%20%20C%20--%3E%20D2%5BVaultSecretAdapter%5D%0A%0A%20%20%20%20B%20--%3E%20E%5Bmodel_config.py%3Cbr%3E%20(Typed%20config%20schema)%5D%0A%0A%20%20%20%20D1%20--%3E%7CRead%2FWrite%20JSON%7C%20F%5B(Local%20File)%5D%0A%20%20%20%20D2%20--%3E%7CSecure%20Read%2FWrite%7C%20G%5B(Vault%20KV%20Store)%5D%0A"})]),fallback:e(()=>[...s[0]||(s[0]=[o(" Loading... ",-1)])]),_:1})),s[2]||(s[2]=a(`<h2 id="versioned-config-manager" tabindex="-1">Versioned Config Manager <a class="header-anchor" href="#versioned-config-manager" aria-label="Permalink to &quot;Versioned Config Manager&quot;">​</a></h2><p>A secure and modular Python-based configuration management system with version control and pluggable storage backends.</p><p>Supports:</p><ul><li>✅ File-based config versioning for local/dev use</li><li>🔐 IBM Cloud Secrets Manager for production</li><li>💾 Config rollback, audit, and restore</li><li>🔁 Pluggable adapters via <code>SecretAdapter</code> interface</li></ul><hr><h2 id="📁-project-structure" tabindex="-1">📁 Project Structure <a class="header-anchor" href="#📁-project-structure" aria-label="Permalink to &quot;📁 Project Structure&quot;">​</a></h2><div class="language- line-numbers-mode"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki material-theme-palenight vp-code" tabindex="0"><code><span class="line"><span>config-manager/</span></span>
<span class="line"><span>├── base_adapter.py # Abstract SecretAdapter interface</span></span>
<span class="line"><span>├── file_loader.py # File-based storage adapter</span></span>
<span class="line"><span>├── vault_loader.py # (Optional) Vault-based adapter</span></span>
<span class="line"><span>├── ibm_secret_loader.py # IBM Cloud Secrets Manager adapter</span></span>
<span class="line"><span>├── config_manager.py # Core version manager</span></span>
<span class="line"><span>├── model_config.py # Typed config schema (pydantic)</span></span>
<span class="line"><span>└── main.py # Example usage</span></span></code></pre><div class="line-numbers-wrapper" aria-hidden="true"><span class="line-number">1</span><br><span class="line-number">2</span><br><span class="line-number">3</span><br><span class="line-number">4</span><br><span class="line-number">5</span><br><span class="line-number">6</span><br><span class="line-number">7</span><br><span class="line-number">8</span><br></div></div><h2 id="installation" tabindex="-1">Installation <a class="header-anchor" href="#installation" aria-label="Permalink to &quot;Installation&quot;">​</a></h2><div class="language-bash line-numbers-mode"><button title="Copy Code" class="copy"></button><span class="lang">bash</span><pre class="shiki material-theme-palenight vp-code" tabindex="0"><code><span class="line"><span style="color:#FFCB6B;">pip</span><span style="color:#C3E88D;"> install</span><span style="color:#C3E88D;"> ibm-secrets-manager</span><span style="color:#C3E88D;"> ibm-cloud-sdk-core</span><span style="color:#C3E88D;"> pydantic</span><span style="color:#C3E88D;"> pydantic-settings</span></span></code></pre><div class="line-numbers-wrapper" aria-hidden="true"><span class="line-number">1</span><br></div></div><h2 id="components" tabindex="-1">Components <a class="header-anchor" href="#components" aria-label="Permalink to &quot;Components&quot;">​</a></h2><ol><li>model_config.py</li></ol><ul><li><p>Defines typed configuration schema using pydantic.RootModel to model various MCP server types.</p></li><li><p>Supports OpenAPI, GraphQL, HTTP, SSE endpoints.</p></li><li><p>Supports flexible authentication formats (bearer, dynamic bearer).</p></li></ul><ol start="2"><li>base_config.py</li></ol><ul><li><p>Defines base configuration schema using pydantic.BaseModel.</p></li><li><p>AppConfig: App-level environment config using pydantic-settings.</p></li><li><p>SecretAdapter: Abstract base class for secret management adapters.</p></li></ul><ol start="3"><li>file_loader.py</li></ol><ul><li><p>Concrete implementation of SecretAdapter that stores versioned configs in a local JSON file.</p></li><li><p>Good for local dev/test.</p></li><li><p>Implements: save, load, get_all_versions, rollback.</p></li></ul><ol start="4"><li>vault_loader.py</li></ol><ul><li>Concrete implementation using HashiCorp Vault for secure storage.</li><li>Reads/writes using hvac client.</li><li>Good for production use.</li><li>Path is namespaced with versioned-configs/{server_id}.</li></ul><ol start="5"><li>config_manager.py</li></ol><ul><li>Handles all orchestration:</li><li>Saves config versions.</li><li>Fetches latest.</li><li>Rolls back to specific version.</li><li>Delegates persistence to injected SecretAdapter.</li></ul><p>🔁 Flow: Save and Rollback Config</p><ul><li>Client loads a ServerModel and calls ConfigManager.save_version().</li><li>ConfigManager appends version metadata (UUID, timestamp).</li><li>Delegates to appropriate adapter (FileSecretAdapter or VaultSecretAdapter).</li><li>Versions are capped by a history_limit.</li><li>To rollback, ConfigManager.rollback() finds and returns the matching version.</li></ul><p>⚙️ Environment Variables</p><table tabindex="0"><thead><tr><th>Variable</th><th>Purpose</th><th>Example</th></tr></thead><tbody><tr><td>USE_VAULT</td><td>Flag</td><td>to switch between file/Vault mode &quot;true&quot;</td></tr><tr><td>VAULT_ADDR</td><td>Vault URL</td><td>&quot;<a href="http://localhost:8200" target="_blank" rel="noreferrer">http://localhost:8200</a>&quot;</td></tr><tr><td>VAULT_TOKEN</td><td>Vault authentication token</td><td>&quot;s.abc123xyz&quot;</td></tr><tr><td>VERSION_CONFIG_FILE_PATH</td><td>Local JSON file path</td><td>&quot;config/versioned_config.json&quot;</td></tr></tbody></table><h2 id="advantages" tabindex="-1">Advantages <a class="header-anchor" href="#advantages" aria-label="Permalink to &quot;Advantages&quot;">​</a></h2><ul><li>Secure version storage via Vault.</li><li>Easy local testing with JSON file.</li><li>Type-safe schema using pydantic.</li><li>Supports config versioning + rollback.</li><li>Easily extensible for AWS Secrets Manager, S3, Consul, etc.</li></ul><h2 id="environment-optional" tabindex="-1">Environment (optional) <a class="header-anchor" href="#environment-optional" aria-label="Permalink to &quot;Environment (optional)&quot;">​</a></h2><div class="language- line-numbers-mode"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki material-theme-palenight vp-code" tabindex="0"><code><span class="line"><span>export VERSION_CONFIG_FILE_PATH=&quot;./versioned_config.json&quot;</span></span></code></pre><div class="line-numbers-wrapper" aria-hidden="true"><span class="line-number">1</span><br></div></div><h2 id="example" tabindex="-1">Example <a class="header-anchor" href="#example" aria-label="Permalink to &quot;Example&quot;">​</a></h2><div class="language- line-numbers-mode"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki material-theme-palenight vp-code" tabindex="0"><code><span class="line"><span>from file_loader import FileSecretAdapter</span></span>
<span class="line"><span>from config_manager import ConfigManager</span></span>
<span class="line"><span></span></span>
<span class="line"><span>adapter = FileSecretAdapter()</span></span>
<span class="line"><span>manager = ConfigManager(adapter)</span></span>
<span class="line"><span></span></span>
<span class="line"><span>cfg = {&quot;db_url&quot;: &quot;sqlite:///test.db&quot;, &quot;debug&quot;: True}</span></span>
<span class="line"><span>vid = manager.save_version(&quot;my-service&quot;, cfg)</span></span>
<span class="line"><span>print(&quot;Saved version:&quot;, vid)</span></span>
<span class="line"><span></span></span>
<span class="line"><span>latest = manager.get_latest_version(&quot;my-service&quot;)</span></span>
<span class="line"><span>print(&quot;Latest config:&quot;, latest)</span></span></code></pre><div class="line-numbers-wrapper" aria-hidden="true"><span class="line-number">1</span><br><span class="line-number">2</span><br><span class="line-number">3</span><br><span class="line-number">4</span><br><span class="line-number">5</span><br><span class="line-number">6</span><br><span class="line-number">7</span><br><span class="line-number">8</span><br><span class="line-number">9</span><br><span class="line-number">10</span><br><span class="line-number">11</span><br><span class="line-number">12</span><br></div></div><h3 id="required-environment-variables" tabindex="-1">Required Environment Variables <a class="header-anchor" href="#required-environment-variables" aria-label="Permalink to &quot;Required Environment Variables&quot;">​</a></h3><div class="language- line-numbers-mode"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki material-theme-palenight vp-code" tabindex="0"><code><span class="line"><span>export IBM_CLOUD_SM_APIKEY=&quot;&lt;your-api-key&gt;&quot;</span></span>
<span class="line"><span>export IBM_CLOUD_SM_URL=&quot;https://&lt;region&gt;.secrets-manager.appdomain.cloud&quot;</span></span>
<span class="line"><span>export IBM_CLOUD_SM_INSTANCE_ID=&quot;&lt;your-instance-guid&gt;&quot;</span></span>
<span class="line"><span>export IBM_CLOUD_SM_SECRET_GROUP=&quot;default&quot;</span></span></code></pre><div class="line-numbers-wrapper" aria-hidden="true"><span class="line-number">1</span><br><span class="line-number">2</span><br><span class="line-number">3</span><br><span class="line-number">4</span><br></div></div><h2 id="add-your-own-adapter" tabindex="-1">Add Your Own Adapter <a class="header-anchor" href="#add-your-own-adapter" aria-label="Permalink to &quot;Add Your Own Adapter&quot;">​</a></h2><p>To add a new backend (e.g., AWS Secrets Manager, S3, DB):</p><p>Inherit from SecretAdapter in base_adapter.py</p><p>Implement 5 methods:</p><ul><li><p>load_config()</p></li><li><p>save_config()</p></li><li><p>get_all_versions()</p></li><li><p>get_latest_version()</p></li><li><p>get_version_by_id()</p></li></ul><h2 id="features" tabindex="-1">Features <a class="header-anchor" href="#features" aria-label="Permalink to &quot;Features&quot;">​</a></h2><ul><li><p>Store JSON/YAML/Pydantic configs</p></li><li><p>Versioned rollback per service</p></li><li><p>Secure secret storage with IBM Secrets Manager</p></li><li><p>Testable in local or production environments</p></li><li><p>Typed configs with pydantic</p></li></ul><h2 id="sample-loader-for-ibm-cloud-secret-manager" tabindex="-1">Sample Loader for IBM Cloud Secret Manager <a class="header-anchor" href="#sample-loader-for-ibm-cloud-secret-manager" aria-label="Permalink to &quot;Sample Loader for IBM Cloud Secret Manager&quot;">​</a></h2><div class="language- line-numbers-mode"><button title="Copy Code" class="copy"></button><span class="lang"></span><pre class="shiki material-theme-palenight vp-code" tabindex="0"><code><span class="line"><span>import os</span></span>
<span class="line"><span>import json</span></span>
<span class="line"><span>import logging</span></span>
<span class="line"><span>from typing import Dict, List, Optional, Any</span></span>
<span class="line"><span></span></span>
<span class="line"><span>from ibm_cloud_sdk_core.authenticators import IAMAuthenticator</span></span>
<span class="line"><span>from ibm_secrets_manager_sdk.secrets_manager_v1 import *</span></span>
<span class="line"><span>from mcp_composer.settings.base_adapter import SecretAdapter</span></span>
<span class="line"><span></span></span>
<span class="line"><span>logger = logging.getLogger(__name__)</span></span>
<span class="line"><span>logging.basicConfig(level=logging.INFO)</span></span>
<span class="line"><span></span></span>
<span class="line"><span></span></span>
<span class="line"><span>class IBMCloudSecretAdapter(SecretAdapter):</span></span>
<span class="line"><span>    &quot;&quot;&quot;</span></span>
<span class="line"><span>    Adapter for IBM Cloud Secrets Manager to store versioned configurations.</span></span>
<span class="line"><span>    Required ENV:</span></span>
<span class="line"><span>        - IBM_CLOUD_SM_APIKEY</span></span>
<span class="line"><span>        - IBM_CLOUD_SM_URL</span></span>
<span class="line"><span>        - IBM_CLOUD_SM_INSTANCE_ID</span></span>
<span class="line"><span>        - (optional) IBM_CLOUD_SM_SECRET_GROUP</span></span>
<span class="line"><span>    &quot;&quot;&quot;</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def __init__(</span></span>
<span class="line"><span>        self,</span></span>
<span class="line"><span>        api_key: str = None,</span></span>
<span class="line"><span>        sm_url: str = None,</span></span>
<span class="line"><span>        instance_id: str = None,</span></span>
<span class="line"><span>        secret_group: str = &quot;default&quot;,</span></span>
<span class="line"><span>        history_limit: int = 10,</span></span>
<span class="line"><span>    ):</span></span>
<span class="line"><span>        self.api_key = api_key or os.getenv(&quot;IBM_CLOUD_SM_APIKEY&quot;)</span></span>
<span class="line"><span>        self.sm_url = sm_url or os.getenv(&quot;IBM_CLOUD_SM_URL&quot;)</span></span>
<span class="line"><span>        self.instance_id = instance_id or os.getenv(&quot;IBM_CLOUD_SM_INSTANCE_ID&quot;)</span></span>
<span class="line"><span>        self.secret_group = secret_group or os.getenv(&quot;IBM_CLOUD_SM_SECRET_GROUP&quot;, &quot;default&quot;)</span></span>
<span class="line"><span>        self.history_limit = history_limit</span></span>
<span class="line"><span>        self.client = self._connect()</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def _connect(self):</span></span>
<span class="line"><span>        authenticator = IAMAuthenticator(self.api_key)</span></span>
<span class="line"><span>        client = SecretsManagerV1(authenticator=authenticator)</span></span>
<span class="line"><span>        client.set_service_url(self.sm_url)</span></span>
<span class="line"><span>        logger.info(&quot;Connected to IBM Secrets Manager at %s&quot;, self.sm_url)</span></span>
<span class="line"><span>        return client</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def _secret_name(self, server_id: str) -&gt; str:</span></span>
<span class="line"><span>        return f&quot;versioned-config-{server_id}&quot;</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def _get_secret_by_name(self, name: str) -&gt; Optional[Dict[str, Any]]:</span></span>
<span class="line"><span>        try:</span></span>
<span class="line"><span>            secrets = self.client.list_secrets(secret_group_name=self.secret_group).get_result()</span></span>
<span class="line"><span>            for secret in secrets.get(&quot;secrets&quot;, []):</span></span>
<span class="line"><span>                if secret.get(&quot;name&quot;) == name:</span></span>
<span class="line"><span>                    return self.client.get_secret(id=secret[&quot;id&quot;]).get_result()</span></span>
<span class="line"><span>        except Exception as e:</span></span>
<span class="line"><span>            logger.warning(&quot;Error finding secret &#39;%s&#39;: %s&quot;, name, e)</span></span>
<span class="line"><span>        return None</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def save_config(self, server_id: str, versions: List[Dict[str, Any]]) -&gt; None:</span></span>
<span class="line"><span>        payload = json.dumps(versions[-self.history_limit:])</span></span>
<span class="line"><span>        name = self._secret_name(server_id)</span></span>
<span class="line"><span>        secret = self._get_secret_by_name(name)</span></span>
<span class="line"><span></span></span>
<span class="line"><span>        resource = SecretResource(payload=payload)</span></span>
<span class="line"><span></span></span>
<span class="line"><span>        if secret:</span></span>
<span class="line"><span>            secret_id = secret[&quot;resources&quot;][0][&quot;id&quot;]</span></span>
<span class="line"><span>            self.client.update_secret(</span></span>
<span class="line"><span>                id=secret_id,</span></span>
<span class="line"><span>                secret_update=UpdateSecretOptions(</span></span>
<span class="line"><span>                    secret_type=&quot;arbitrary&quot;,</span></span>
<span class="line"><span>                    metadata=UpdateSecretMetadata(secret_group_id=self.secret_group, name=name),</span></span>
<span class="line"><span>                    resources=[UpdateSecretResource(payload=payload)],</span></span>
<span class="line"><span>                )</span></span>
<span class="line"><span>            )</span></span>
<span class="line"><span>            logger.info(&quot;Updated secret: %s&quot;, name)</span></span>
<span class="line"><span>        else:</span></span>
<span class="line"><span>            self.client.create_secret(</span></span>
<span class="line"><span>                secret_type=&quot;arbitrary&quot;,</span></span>
<span class="line"><span>                secret=CreateSecretOptions(</span></span>
<span class="line"><span>                    metadata=SecretMetadata(secret_group_id=self.secret_group, name=name),</span></span>
<span class="line"><span>                    resources=[resource],</span></span>
<span class="line"><span>                ),</span></span>
<span class="line"><span>                headers={&quot;X-Sm-Instance-Id&quot;: self.instance_id}</span></span>
<span class="line"><span>            )</span></span>
<span class="line"><span>            logger.info(&quot;Created new secret: %s&quot;, name)</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def get_all_versions(self, server_id: str) -&gt; List[Dict[str, Any]]:</span></span>
<span class="line"><span>        secret = self._get_secret_by_name(self._secret_name(server_id))</span></span>
<span class="line"><span>        if secret:</span></span>
<span class="line"><span>            try:</span></span>
<span class="line"><span>                payload = secret[&quot;resources&quot;][0].get(&quot;payload&quot;, &quot;[]&quot;)</span></span>
<span class="line"><span>                return json.loads(payload)</span></span>
<span class="line"><span>            except Exception as e:</span></span>
<span class="line"><span>                logger.warning(&quot;Error parsing payload: %s&quot;, e)</span></span>
<span class="line"><span>        return []</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def get_latest_version(self, server_id: str) -&gt; Optional[Dict[str, Any]]:</span></span>
<span class="line"><span>        versions = self.get_all_versions(server_id)</span></span>
<span class="line"><span>        return versions[-1] if versions else None</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def get_version_by_id(self, server_id: str, version_id: str) -&gt; Optional[Dict[str, Any]]:</span></span>
<span class="line"><span>        for version in self.get_all_versions(server_id):</span></span>
<span class="line"><span>            if version.get(&quot;version_id&quot;) == version_id:</span></span>
<span class="line"><span>                return version</span></span>
<span class="line"><span>        return None</span></span>
<span class="line"><span></span></span>
<span class="line"><span>    def load_config(self, server_id: str) -&gt; Dict[str, Any]:</span></span>
<span class="line"><span>        latest = self.get_latest_version(server_id)</span></span>
<span class="line"><span>        return latest.get(&quot;config&quot;, {}) if latest else {}</span></span></code></pre><div class="line-numbers-wrapper" aria-hidden="true"><span class="line-number">1</span><br><span class="line-number">2</span><br><span class="line-number">3</span><br><span class="line-number">4</span><br><span class="line-number">5</span><br><span class="line-number">6</span><br><span class="line-number">7</span><br><span class="line-number">8</span><br><span class="line-number">9</span><br><span class="line-number">10</span><br><span class="line-number">11</span><br><span class="line-number">12</span><br><span class="line-number">13</span><br><span class="line-number">14</span><br><span class="line-number">15</span><br><span class="line-number">16</span><br><span class="line-number">17</span><br><span class="line-number">18</span><br><span class="line-number">19</span><br><span class="line-number">20</span><br><span class="line-number">21</span><br><span class="line-number">22</span><br><span class="line-number">23</span><br><span class="line-number">24</span><br><span class="line-number">25</span><br><span class="line-number">26</span><br><span class="line-number">27</span><br><span class="line-number">28</span><br><span class="line-number">29</span><br><span class="line-number">30</span><br><span class="line-number">31</span><br><span class="line-number">32</span><br><span class="line-number">33</span><br><span class="line-number">34</span><br><span class="line-number">35</span><br><span class="line-number">36</span><br><span class="line-number">37</span><br><span class="line-number">38</span><br><span class="line-number">39</span><br><span class="line-number">40</span><br><span class="line-number">41</span><br><span class="line-number">42</span><br><span class="line-number">43</span><br><span class="line-number">44</span><br><span class="line-number">45</span><br><span class="line-number">46</span><br><span class="line-number">47</span><br><span class="line-number">48</span><br><span class="line-number">49</span><br><span class="line-number">50</span><br><span class="line-number">51</span><br><span class="line-number">52</span><br><span class="line-number">53</span><br><span class="line-number">54</span><br><span class="line-number">55</span><br><span class="line-number">56</span><br><span class="line-number">57</span><br><span class="line-number">58</span><br><span class="line-number">59</span><br><span class="line-number">60</span><br><span class="line-number">61</span><br><span class="line-number">62</span><br><span class="line-number">63</span><br><span class="line-number">64</span><br><span class="line-number">65</span><br><span class="line-number">66</span><br><span class="line-number">67</span><br><span class="line-number">68</span><br><span class="line-number">69</span><br><span class="line-number">70</span><br><span class="line-number">71</span><br><span class="line-number">72</span><br><span class="line-number">73</span><br><span class="line-number">74</span><br><span class="line-number">75</span><br><span class="line-number">76</span><br><span class="line-number">77</span><br><span class="line-number">78</span><br><span class="line-number">79</span><br><span class="line-number">80</span><br><span class="line-number">81</span><br><span class="line-number">82</span><br><span class="line-number">83</span><br><span class="line-number">84</span><br><span class="line-number">85</span><br><span class="line-number">86</span><br><span class="line-number">87</span><br><span class="line-number">88</span><br><span class="line-number">89</span><br><span class="line-number">90</span><br><span class="line-number">91</span><br><span class="line-number">92</span><br><span class="line-number">93</span><br><span class="line-number">94</span><br><span class="line-number">95</span><br><span class="line-number">96</span><br><span class="line-number">97</span><br><span class="line-number">98</span><br><span class="line-number">99</span><br><span class="line-number">100</span><br><span class="line-number">101</span><br><span class="line-number">102</span><br><span class="line-number">103</span><br><span class="line-number">104</span><br><span class="line-number">105</span><br><span class="line-number">106</span><br><span class="line-number">107</span><br><span class="line-number">108</span><br><span class="line-number">109</span><br><span class="line-number">110</span><br></div></div>`,41))])}const y=l(d,[["render",b]]);export{q as __pageData,y as default};
