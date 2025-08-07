import yaml
import json
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from typing import List, Dict, Optional, Any

from .schemas import ApiClient, ErrorDetail, ErrorResponse

class AccessRule(BaseModel):
    path_pattern: str
    methods: List[str] = ["*"]
    enforce_owner: Optional[str] = None

class SecureEnclaveConfig(BaseModel):
    provider: str
    require_attestation: bool

class SelfLearningConfig(BaseModel):
    enabled: bool
    feedback_sink: str

class DynamicAccessTier(BaseModel):
    risk_threshold: float
    action: str
    throttle_limit: Optional[str] = None
    captcha_provider_url: Optional[str] = None

class ApiDiscoveryConfig(BaseModel):
    openapi_spec_url: str
    on_shadow_api_discovered: str

class LogShippingConfig(BaseModel):
    enabled: bool
    endpoint: str
    auth_token: str

class AuthPolicy(BaseModel):
    name: str
    match: Dict[str, Any]
    rules: List[AccessRule]

class BehavioralAnalysisConfig(BaseModel):
    enforce_header_consistency: bool
    max_path_entropy: float

class AIModelConfig(BaseModel):
    path: str
    high_risk_threshold: float

class SentryRule(BaseModel):
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    pattern: Optional[str] = None
    max_depth: Optional[int] = None
    inspect_locations: List[str] = []
    action: str
    enforce_owner: Optional[str] = None

class PIIScanPolicy(BaseModel):
    role: str
    redact_entities: List[str]

class Query(BaseModel):
    name: str
    http_method: str
    backend_url: str
    adapter: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None

class Aggregation(BaseModel):
    public_path: str
    required_role: str
    queries: List[Query]

class ApiClient(BaseModel):
    client_id: str
    api_key: str
    role: str
    allowed_ips: List[str] = []


class Settings(BaseSettings):
    jwt_secret_key: str = Field(alias='JWT_SECRET_KEY')
    api_clients_json: str = Field(alias='API_CLIENTS_JSON')
    redis_url: Optional[str] = Field(None, alias='REDIS_URL')

    @property
    def api_clients(self) -> List[ApiClient]:
        """Parses the API_CLIENTS_JSON string into a list of ApiClient objects."""
        return [ApiClient(**c) for c in json.loads(self.api_clients_json)]
 
    @property
    def abuseipdb_api_key(self) -> str:
        return self._load_yaml().get('abuseipdb_api_key', '')
        
    @property
    def abuseipdb_confidence_minimum(self) -> int:
        return self._load_yaml().get('abuseipdb_confidence_minimum', 95)
        
    @property
    def audit_log_signing_key(self) -> str:
        return self._load_yaml().get('audit_log_signing_key', '')

    @property
    def api_discovery(self) -> ApiDiscoveryConfig:
        return ApiDiscoveryConfig(**self._load_yaml().get('api_discovery', {}))

    @property
    def log_shipping(self) -> LogShippingConfig:
        return LogShippingConfig(**self._load_yaml().get('log_shipping', {}))

    @property
    def backend_target_url(self) -> str:
        return self._load_yaml().get('backend_target_url', '')

    @property
    def authorization_policies(self) -> List[AuthPolicy]:
        return [AuthPolicy(**p) for p in self._load_yaml().get('authorization_policies', [])]

    @property
    def behavioral_analysis(self) -> BehavioralAnalysisConfig:
        return BehavioralAnalysisConfig(**self._load_yaml().get('behavioral_analysis', {}))

    @property
    def adaptive_security_model(self) -> AIModelConfig:
        return AIModelConfig(**self._load_yaml().get('adaptive_security_model', {}))

    @property
    def sentry_rules(self) -> List[SentryRule]:
        """Loads and validates the 'sentry_rules' (WAF) section from config.yaml."""
        config = self._load_yaml()
        rules_data = config.get('sentry_rules', [])
        return [SentryRule(**r) for r in rules_data]

    @property
    def pii_scan_policy(self) -> List[PIIScanPolicy]:
        return [PIIScanPolicy(**p) for p in self._load_yaml().get('pii_scan_policy', [])]

    @property
    def egress_allowlist(self) -> List[str]:
        return self._load_yaml().get('egress_allowlist', [])
        
    @property
    def aggregations(self) -> List[Aggregation]:
        return [Aggregation(**a) for a in self._load_yaml().get('aggregations', [])]

    def _load_yaml(self, path: str = "config.yaml") -> Dict:
        if not hasattr(self, '_yaml_config'):
            print(f"Loading and parsing {path}...")
            try:
                with open(path, "r") as f:
                    self._yaml_config = yaml.safe_load(f)
            except FileNotFoundError:
                print(f"ERROR: Configuration file '{path}' not found. Please ensure it exists.")
                exit(1)
        return self._yaml_config

    class Config:
        env_file_encoding = 'utf-8'
