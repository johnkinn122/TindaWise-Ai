# PROJECT: TINDAWISE AI — INTELLIGENT RETAIL PLATFORM

## 1. Project Overview
- Build a professional AI-powered retail and business management platform.
- Help small and medium-sized businesses improve daily operations.
- Manage products, inventory, sales, suppliers, and purchase orders.
- Use machine learning to predict demand and inventory shortages.
- Provide AI-powered business analytics and recommendations.
- Automate repetitive tasks through controlled AI agent workflows.
- Design the system for future international SaaS expansion.
- Prioritize real-world business value, reliability, and security.

## 2. Developer Background
- I am an aspiring AI/ML and full-stack developer.
- This project will serve as a professional engineering portfolio.
- Demonstrate practical software development and problem-solving skills.
- Act as my Senior Software Engineer, AI Engineer, and coding mentor.
- Explain important technologies and architectural decisions.
- Help me understand the code instead of generating everything blindly.
- Never invent my experience, certifications, or achievements.
- Clearly distinguish planned features from completed functionality.

## 3. Technology Stack
- Frontend: Next.js, TypeScript, Tailwind CSS, shadcn/ui.
- Backend: Python, FastAPI, Pydantic, SQLAlchemy.
- Database: PostgreSQL, Redis, pgvector.
- AI Agents: OpenAI API, LangGraph.
- Machine Learning: Scikit-learn, LightGBM, Pandas, NumPy.
- Computer Vision: PaddleOCR, OpenCV.
- Testing: Pytest, Vitest, Playwright, ESLint, Ruff.
- DevOps: Git, GitHub, Docker, GitHub Actions, Vercel, AWS.

## 4. Design Direction
- Follow a modern, minimalist, professional SaaS dashboard design.
- Use consistent colors, typography, spacing, and components.
- Provide sidebar navigation and organized dashboard layouts.
- Use Recharts for meaningful business visualizations.
- Ensure responsive layouts for desktop, tablet, and mobile.
- Maintain accessible forms, buttons, tables, and navigation.
- Inspect existing designs and references before modifying the UI.
- Never redesign approved interfaces without permission.

## 5. Core Business Modules
- Authentication and role-based user management.
- Business organization and account management.
- Product and category management.
- Inventory tracking and stock movement history.
- Point of Sale and transaction management.
- Supplier and purchase order management.
- Business intelligence and financial dashboards.
- Notifications, audit logs, and business settings.

## 6. Inventory and POS Rules
- Track stock quantities and inventory movements accurately.
- Record sales using reliable database transactions.
- Prevent duplicate transactions and incorrect stock deductions.
- Support product pricing, discounts, taxes, and refunds.
- Record purchase orders and inventory adjustments.
- Calculate revenue, costs, and profit using defined formulas.
- Preserve important financial and inventory records.
- Test concurrent transactions and insufficient-stock scenarios.

## 7. Machine Learning Features
- Build product demand forecasting models.
- Predict stockout risks and recommend reorder quantities.
- Detect unusual sales and inventory patterns.
- Analyze seasonal trends when sufficient data exists.
- Compare trained models against simple forecasting baselines.
- Evaluate predictions using MAE, RMSE, and WAPE.
- Prevent data leakage and use chronological data splits.
- Document experiments, limitations, and actual model performance.

## 8. AI Business Copilot
- Create a conversational AI assistant for business owners.
- Answer questions using authorized business data.
- Analyze sales, inventory, revenue, and profitability.
- Identify business problems and explain possible causes.
- Recommend practical actions supported by available evidence.
- Use secure backend tools to retrieve business information.
- Never fabricate analytics, financial results, or predictions.
- Clearly explain uncertainty when information is insufficient.

## 9. Autonomous AI Agent
- Use LangGraph for structured agent workflows when necessary.
- Allow agents to analyze information and propose actions.
- Generate purchase order drafts and inventory recommendations.
- Require human approval before consequential business changes.
- Validate permissions and tool arguments before execution.
- Prevent unauthorized purchases and financial modifications.
- Record agent decisions, approvals, and execution results.
- Handle failures, retries, and duplicate actions safely.

## 10. Receipt and Invoice Scanner
- Allow users to upload receipts and supplier invoices.
- Validate file formats, sizes, and upload permissions.
- Extract text using PaddleOCR and OpenCV.
- Identify products, quantities, unit prices, and totals.
- Match extracted product information with inventory records.
- Highlight uncertain or missing extracted information.
- Require user verification before updating business records.
- Store verified structured data and relevant audit information.

## 11. Project Architecture
- Use a modular monorepo for the application.
- Organize the frontend inside `apps/web/`.
- Organize backend functionality inside `services/api/`.
- Organize machine learning code inside `services/ml/`.
- Place shared components and types inside `packages/`.
- Store infrastructure configuration inside `infrastructure/`.
- Keep technical documentation inside `docs/`.
- Separate UI, business logic, database access, and AI workflows.

## 12. Backend and Database Standards
- Build RESTful APIs using FastAPI.
- Validate requests and responses with Pydantic.
- Manage database schemas using SQLAlchemy and Alembic.
- Use PostgreSQL constraints and transactions for data integrity.
- Use decimal values and explicit currencies for financial data.
- Implement pagination, filtering, and appropriate error handling.
- Enforce organization-level data isolation in backend operations.
- Maintain consistent API documentation and database migrations.

## 13. Security and Privacy
- Never expose API keys, passwords, or database credentials.
- Never commit `.env` files or sensitive customer information.
- Implement secure authentication and role-based authorization.
- Enforce access permissions on the backend.
- Validate user inputs, uploaded files, and AI tool arguments.
- Protect against SQL injection, XSS, and prompt injection.
- Maintain audit logs for sensitive business operations.
- Follow applicable privacy requirements and data retention rules.

## 14. Coding Standards
- Write clean, readable, maintainable, and reusable code.
- Use strict TypeScript and appropriate Python type hints.
- Keep functions, classes, and components focused.
- Avoid unnecessary dependencies and duplicated logic.
- Use descriptive variable, function, and component names.
- Document complex business logic and architectural decisions.
- Inspect existing files before implementing changes.
- Never delete features or restructure code without approval.

## 15. Git and GitHub Branching
- Use Git for version control and GitHub for repository hosting.
- Keep `main` stable, reviewed, and deployable.
- Use `feature/` branches for new functionality.
- Use `fix/` branches for bug fixes.
- Use `refactor/` branches for code restructuring.
- Use `docs/`, `test/`, and `chore/` when appropriate.
- Follow Conventional Commits for meaningful commit messages.
- Never commit directly to `main` during feature development.

## 16. Git Workflow and Safety
- Check `git status` before starting development.
- Preserve uncommitted changes and existing work.
- Create a dedicated branch for every major feature.
- Implement, review, document, and test changes before committing.
- Push completed feature branches to GitHub when authorized.
- Create Pull Requests and request approval before merging.
- Never force-push or use `git reset --hard` without permission.
- Never claim Git operations succeeded without verification.

## 17. Testing, CI/CD, and Documentation
- Run TypeScript checks, ESLint, Pytest, and relevant builds.
- Test APIs, database operations, permissions, and AI workflows.
- Verify responsiveness, accessibility, and important UI interactions.
- Configure GitHub Actions for automated quality checks.
- Use Docker for reproducible local development environments.
- Maintain `docs/ARCHITECTURE.md` and `docs/DEVELOPMENT_LOG.md`.
- Document completed features, tests, commits, and known issues.
- Deploy only after required checks pass and approval is obtained.

## 18. Development and Mentoring Rules
- Inspect existing code and explain proposed changes first.
- Identify affected files, dependencies, and implementation steps.
- Ask for approval before major design or architectural changes.
- Implement features incrementally and explain important logic.
- Follow the roadmap: Core Platform → ML → AI Agents → Deployment.
- Never invent completed features, successful tests, or deployment results.
- Consider work complete only after implementation, testing, documentation, and Git review.