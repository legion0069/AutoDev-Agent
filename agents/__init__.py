"""
AutoDev Agents Package (v3.4 Enterprise AI Organization)
========================================================
Includes classic agents, specialized collaborative engineering agents,
and Version 3.4 autonomous department AI agents:
CEOAgent, CTOAgent, EngineeringManagerAgent, ArchitectAgent,
BackendTeamAgent, FrontendTeamAgent, QAManagerAgent, SecurityManagerAgent,
DevOpsManagerAgent, ReleaseManagerAgent, ProductManagerAgent, BusinessAnalystAgent,
DocumentationManagerAgent, CustomerFeedbackManagerAgent, FinanceManagerAgent,
ComplianceManagerAgent, OperationsManagerAgent.
"""

from .specialized_agent import SpecializedAgent
from .architecture_agent import ArchitectureAgent
from .backend_agent import BackendAgent
from .frontend_agent import FrontendAgent
from .testing_agent import TestingAgent
from .security_agent import SecurityAgent
from .performance_agent import PerformanceAgent
from .documentation_agent import DocumentationAgent
from .release_agent import ReleaseAgent

# AutoDev Version 3.4 Organizational Agents
from .ceo_agent import CEOAgent
from .cto_agent import CTOAgent
from .engineering_manager import EngineeringManagerAgent
from .architect_agent import ArchitectAgent
from .backend_team import BackendTeamAgent
from .frontend_team import FrontendTeamAgent
from .qa_manager import QAManagerAgent
from .security_manager import SecurityManagerAgent
from .devops_manager import DevOpsManagerAgent
from .release_manager import ReleaseManagerAgent
from .product_manager import ProductManagerAgent
from .business_analyst import BusinessAnalystAgent
from .documentation_manager import DocumentationManagerAgent
from .customer_feedback_manager import CustomerFeedbackManagerAgent
from .finance_manager import FinanceManagerAgent
from .compliance_manager import ComplianceManagerAgent
from .operations_manager import OperationsManagerAgent

# AutoDev Version 3.5 Federation Agents
from .federation_ceo import FederationCEO, FederationCEOAgent
from .federation_cto import FederationCTO, FederationCTOAgent
from .portfolio_director import PortfolioDirector, PortfolioDirectorAgent
from .global_architect import GlobalArchitect, GlobalArchitectAgent
from .cross_company_coordinator import CrossCompanyCoordinator, CrossCompanyCoordinatorAgent
from .enterprise_security_officer import EnterpriseSecurityOfficer, EnterpriseSecurityOfficerAgent
from .chief_financial_officer import ChiefFinancialOfficer, ChiefFinancialOfficerAgent
from .enterprise_risk_officer import EnterpriseRiskOfficer, EnterpriseRiskOfficerAgent
from .enterprise_auditor import EnterpriseAuditor, EnterpriseAuditorAgent
from .global_operations_director import GlobalOperationsDirector, GlobalOperationsDirectorAgent

# AutoDev Version 3.6 Autonomous AI Research Lab Agents
from .chief_scientist import ChiefScientistAgent
from .principal_researcher import PrincipalResearcherAgent
from .experiment_designer import ExperimentDesignerAgent
from .statistical_analyst import StatisticalAnalystAgent
from .benchmark_engineer import BenchmarkEngineerAgent
from .algorithm_architect import AlgorithmArchitectAgent
from .peer_reviewer import PeerReviewerAgent
from .patent_specialist import PatentSpecialistAgent
from .paper_author import PaperAuthorAgent
from .research_curator import ResearchCuratorAgent

__all__ = [
    "SpecializedAgent",
    "ArchitectureAgent",
    "BackendAgent",
    "FrontendAgent",
    "TestingAgent",
    "SecurityAgent",
    "PerformanceAgent",
    "DocumentationAgent",
    "ReleaseAgent",
    # Version 3.4 Organization Agents
    "CEOAgent",
    "CTOAgent",
    "EngineeringManagerAgent",
    "ArchitectAgent",
    "BackendTeamAgent",
    "FrontendTeamAgent",
    "QAManagerAgent",
    "SecurityManagerAgent",
    "DevOpsManagerAgent",
    "ReleaseManagerAgent",
    "ProductManagerAgent",
    "BusinessAnalystAgent",
    "DocumentationManagerAgent",
    "CustomerFeedbackManagerAgent",
    "FinanceManagerAgent",
    "ComplianceManagerAgent",
    "OperationsManagerAgent",
    # Version 3.5 Federation Agents
    "FederationCEO",
    "FederationCEOAgent",
    "FederationCTO",
    "FederationCTOAgent",
    "PortfolioDirector",
    "PortfolioDirectorAgent",
    "GlobalArchitect",
    "GlobalArchitectAgent",
    "CrossCompanyCoordinator",
    "CrossCompanyCoordinatorAgent",
    "EnterpriseSecurityOfficer",
    "EnterpriseSecurityOfficerAgent",
    "ChiefFinancialOfficer",
    "ChiefFinancialOfficerAgent",
    "EnterpriseRiskOfficer",
    "EnterpriseRiskOfficerAgent",
    "EnterpriseAuditor",
    "EnterpriseAuditorAgent",
    "GlobalOperationsDirector",
    "GlobalOperationsDirectorAgent",
    # Version 3.6 Research Lab Agents
    "ChiefScientistAgent",
    "PrincipalResearcherAgent",
    "ExperimentDesignerAgent",
    "StatisticalAnalystAgent",
    "BenchmarkEngineerAgent",
    "AlgorithmArchitectAgent",
    "PeerReviewerAgent",
    "PatentSpecialistAgent",
    "PaperAuthorAgent",
    "ResearchCuratorAgent",
]
