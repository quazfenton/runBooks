import * as vscode from 'vscode';
import axios from 'axios';

let apiBaseUrl = 'http://localhost:8000';

export function activate(context: vscode.ExtensionContext) {
    console.log('Living Runbooks extension is now active!');

    // Get API URL from settings
    const config = vscode.workspace.getConfiguration('livingRunbooks');
    apiBaseUrl = config.get('api_url') || 'http://localhost:8000';

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('living-runbooks.refresh', () => {
            vscode.window.showInformationMessage('Refreshing runbooks...');
            refreshRunbooks();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('living-runbooks.openRunbook', (item: RunbookItem) => {
            openRunbook(item.path);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('living-runbooks.annotateIncident', (item: RunbookItem) => {
            annotateIncident(item.path);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('living-runbooks.generateSuggestions', (item: RunbookItem) => {
            generateSuggestions(item.path);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('living-runbooks.findSimilarIncidents', () => {
            findSimilarIncidents();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('living-runbooks.generateReport', () => {
            generateReport();
        })
    );

    // Register tree provider
    const runbookProvider = new RunbookTreeProvider();
    vscode.window.registerTreeDataProvider('runbooksView', runbookProvider);

    // Listen for configuration changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(e => {
            if (e.affectsConfiguration('livingRunbooks.api_url')) {
                const config = vscode.workspace.getConfiguration('livingRunbooks');
                apiBaseUrl = config.get('api_url') || 'http://localhost:8000';
            }
        })
    );
}

async function refreshRunbooks() {
    try {
        const response = await axios.get(`${apiBaseUrl}/api/runbooks`);
        vscode.window.showInformationMessage(`Found ${response.data.count} runbooks`);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to refresh: ${error}`);
    }
}

async function openRunbook(path: string) {
    try {
        const response = await axios.get(`${apiBaseUrl}/api/runbooks/${encodeURIComponent(path)}`);
        const doc = await vscode.workspace.openTextDocument({
            content: JSON.stringify(response.data.runbook, null, 2),
            language: 'json'
        });
        await vscode.window.showTextDocument(doc);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to open runbook: ${error}`);
    }
}

async function annotateIncident(path: string) {
    const incidentId = await vscode.window.showInputBox({
        prompt: 'Enter incident ID',
        placeHolder: 'INC-20260303-001'
    });

    if (!incidentId) {
        return;
    }

    const cause = await vscode.window.showInputBox({
        prompt: 'Enter root cause',
        placeHolder: 'Memory leak in service'
    });

    const fix = await vscode.window.showInputBox({
        prompt: 'Enter fix applied',
        placeHolder: 'Increased memory limits'
    });

    if (!cause || !fix) {
        return;
    }

    try {
        await axios.post(`${apiBaseUrl}/api/runbooks/${encodeURIComponent(path)}/annotate`, {
            incident_id: incidentId,
            cause: cause,
            fix: fix
        });
        vscode.window.showInformationMessage('Incident annotated successfully!');
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to annotate: ${error}`);
    }
}

async function generateSuggestions(path: string) {
    vscode.window.showInformationMessage('Generating AI suggestions...');

    try {
        const response = await axios.post(`${apiBaseUrl}/api/ai/suggest`, {
            runbook_path: path,
            incident: {
                cause: 'test',
                fix: 'test'
            }
        });

        const suggestions = response.data.suggestions;
        const suggestionText = suggestions.map((s: any) => 
            `[${s.priority}] ${s.type}: ${s.action}\n   Reason: ${s.reasoning}`
        ).join('\n\n');

        vscode.window.showInformationMessage(`Suggestions:\n\n${suggestionText}`);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to generate suggestions: ${error}`);
    }
}

async function findSimilarIncidents() {
    const query = await vscode.window.showInputBox({
        prompt: 'Enter incident description for similarity search',
        placeHolder: 'database connection timeout'
    });

    if (!query) {
        return;
    }

    try {
        const response = await axios.post(`${apiBaseUrl}/api/ai/correlate`, {
            query: query
        });

        const similar = response.data.similar;
        const similarText = similar.map((s: any) => 
            `[${s.similarity.toFixed(2)}] ${s.service}:${s.incident_id}\n   Cause: ${s.cause}\n   Fix: ${s.fix}`
        ).join('\n\n');

        vscode.window.showInformationMessage(`Similar Incidents:\n\n${similarText}`);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to find similar incidents: ${error}`);
    }
}

async function generateReport() {
    const incidentId = await vscode.window.showInputBox({
        prompt: 'Enter incident ID for report generation',
        placeHolder: 'INC-20260303-001'
    });

    if (!incidentId) {
        return;
    }

    vscode.window.showInformationMessage('Generating post-incident report...');

    try {
        const response = await axios.post(`${apiBaseUrl}/api/ai/report`, {
            incident: {
                incident_id: incidentId
            }
        });

        const report = response.data.report;
        const doc = await vscode.workspace.openTextDocument({
            content: report,
            language: 'markdown'
        });
        await vscode.window.showTextDocument(doc);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to generate report: ${error}`);
    }
}

class RunbookItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly path: string,
        public readonly service: string,
        public readonly annotationsCount: number,
        collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = `${path}\nService: ${service}\nAnnotations: ${annotationsCount}`;
        this.description = `${service} (${annotationsCount} annotations)`;
        this.iconPath = new vscode.ThemeIcon('file-code');
        
        this.command = {
            command: 'living-runbooks.openRunbook',
            title: 'Open Runbook',
            arguments: [this]
        };
    }
}

class RunbookTreeProvider implements vscode.TreeDataProvider<RunbookItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<RunbookItem | undefined | null | void> = new vscode.EventEmitter();
    readonly onDidChangeTreeData: vscode.Event<RunbookItem | undefined | null | void> = this._onDidChangeTreeData.event;

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: RunbookItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: RunbookItem): Promise<RunbookItem[]> {
        if (element) {
            return [];
        }

        try {
            const response = await axios.get(`${apiBaseUrl}/api/runbooks`);
            const runbooks = response.data.runbooks || [];

            return runbooks.map((rb: any) => 
                new RunbookItem(
                    rb.title,
                    rb.path,
                    rb.service,
                    rb.annotations_count,
                    vscode.TreeItemCollapsibleState.None
                )
            );
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to load runbooks: ${error}`);
            return [];
        }
    }
}

export function deactivate() {}
