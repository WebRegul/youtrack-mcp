"""
YouTrack Issue MCP tools.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from youtrack_mcp.api.client import YouTrackClient
from youtrack_mcp.api.issues import IssuesClient
from youtrack_mcp.api.projects import ProjectsClient
from youtrack_mcp.mcp_wrappers import sync_wrapper

logger = logging.getLogger(__name__)


class IssueTools:
    """Issue-related MCP tools."""
    
    def __init__(self):
        """Initialize the issue tools."""
        self.client = YouTrackClient()
        self.issues_api = IssuesClient(self.client)
    
    @sync_wrapper    
    def get_issue(self, issue_id: str) -> str:
        """
        Get information about a specific issue.
        
        FORMAT: get_issue(issue_id="DEMO-123") - You must use the exact parameter name 'issue_id'.
        
        Args:
            issue_id: The issue ID or readable ID (e.g., PROJECT-123)
            
        Returns:
            JSON string with issue information
        """
        try:
            # First try to get the issue data with explicit fields
            fields = "id,summary,description,created,updated,project(id,name,shortName),reporter(id,login,name),assignee(id,login,name),customFields(id,name,value)"
            raw_issue = self.client.get(f"issues/{issue_id}?fields={fields}")
            
            # If we got a minimal response, enhance it with default values
            if isinstance(raw_issue, dict) and raw_issue.get('$type') == 'Issue' and 'summary' not in raw_issue:
                raw_issue['summary'] = f"Issue {issue_id}"  # Provide a default summary
            
            # Return the raw issue data directly - avoid model validation issues
            return json.dumps(raw_issue, indent=2)
            
        except Exception as e:
            logger.exception(f"Error getting issue {issue_id}")
            return json.dumps({"error": str(e)})
    
    @sync_wrapper    
    def search_issues(self, query: str, limit: int = 10) -> str:
        """
        Search for issues using YouTrack query language.
        
        FORMAT: search_issues(query="project: DEMO #Unresolved", limit=10)
        
        Args:
            query: The search query
            limit: Maximum number of issues to return
            
        Returns:
            JSON string with matching issues
        """
        try:
            # Request with explicit fields to get complete data
            fields = "id,summary,description,created,updated,project(id,name,shortName),reporter(id,login,name),assignee(id,login,name),customFields(id,name,value)"
            params = {"query": query, "$top": limit, "fields": fields}
            raw_issues = self.client.get("issues", params=params)
            
            # Return the raw issues data directly
            return json.dumps(raw_issues, indent=2)
            
        except Exception as e:
            logger.exception(f"Error searching issues with query: {query}")
            return json.dumps({"error": str(e)})
    
    @sync_wrapper
    def create_issue(self, project: str, summary: str, description: Optional[str] = None) -> str:
        """
        Create a new issue in YouTrack.
        
        FORMAT: create_issue(project="DEMO", summary="Bug: Login not working", description="Details here")
        
        Args:
            project: The ID or short name of the project
            summary: The issue summary
            description: The issue description (optional)
            
        Returns:
            JSON string with the created issue information
        """
        try:
            # Check if we got proper parameters
            logger.debug(f"Creating issue with: project={project}, summary={summary}, description={description}")
            
            # Handle kwargs format from MCP
            if isinstance(project, dict) and 'project' in project and 'summary' in project:
                # Extract from dict if we got project as a JSON object
                logger.info("Detected project as a dictionary, extracting parameters")
                description = project.get('description', None)
                summary = project.get('summary')
                project = project.get('project')
                
            # Ensure we have valid data
            if not project:
                return json.dumps({"error": "Project is required", "status": "error"})
            if not summary:
                return json.dumps({"error": "Summary is required", "status": "error"})
            
            # Check if project is a project ID or short name
            project_id = project
            if project and not project.startswith("0-"):
                # Try to get the project ID from the short name (e.g., "DEMO")
                try:
                    logger.info(f"Looking up project ID for: {project}")
                    projects_api = ProjectsClient(self.client)
                    project_obj = projects_api.get_project_by_name(project)
                    if project_obj:
                        logger.info(f"Found project {project_obj.name} with ID {project_obj.id}")
                        project_id = project_obj.id
                    else:
                        logger.warning(f"Project not found: {project}")
                        return json.dumps({"error": f"Project not found: {project}", "status": "error"})
                except Exception as e:
                    logger.warning(f"Error finding project: {str(e)}")
                    return json.dumps({"error": f"Error finding project: {str(e)}", "status": "error"})
            
            logger.info(f"Creating issue in project {project_id}: {summary}")
            
            # Call the API client to create the issue
            try:
                issue = self.issues_api.create_issue(project_id, summary, description)
                
                # Check if we got an issue with an ID
                if isinstance(issue, dict) and issue.get('error'):
                    # Handle error returned as a dict
                    return json.dumps(issue)
                
                # Try to get full issue details right after creation
                if hasattr(issue, 'id'):
                    try:
                        # Get the full issue details using issue ID
                        issue_id = issue.id
                        detailed_issue = self.issues_api.get_issue(issue_id)
                        
                        if hasattr(detailed_issue, 'model_dump'):
                            return json.dumps(detailed_issue.model_dump(), indent=2)
                        else:
                            return json.dumps(detailed_issue, indent=2)
                    except Exception as e:
                        logger.warning(f"Could not retrieve detailed issue: {str(e)}")
                        # Fall back to original issue
                
                # Original issue as fallback
                if hasattr(issue, 'model_dump'):
                    return json.dumps(issue.model_dump(), indent=2)
                else:
                    return json.dumps(issue, indent=2)
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'response') and e.response:
                    try:
                        # Try to get detailed error message from response
                        error_content = e.response.content.decode('utf-8', errors='replace')
                        error_msg = f"{error_msg} - {error_content}"
                    except:
                        pass
                logger.error(f"API error creating issue: {error_msg}")
                return json.dumps({"error": error_msg, "status": "error"})
                
        except Exception as e:
            logger.exception(f"Error creating issue in project {project}")
            return json.dumps({"error": str(e), "status": "error"})
    
    @sync_wrapper        
    def add_comment(self, issue_id: str, text: str) -> str:
        """
        Add a comment to an issue.
        
        FORMAT: add_comment(issue_id="DEMO-123", text="This is my comment")
        
        Args:
            issue_id: The issue ID or readable ID
            text: The comment text
            
        Returns:
            JSON string with the result
        """
        try:
            result = self.issues_api.add_comment(issue_id, text)
            return json.dumps(result, indent=2)
        except Exception as e:
            logger.exception(f"Error adding comment to issue {issue_id}")
            return json.dumps({"error": str(e)})
    
    @sync_wrapper
    def get_comments(self, issue_id: str, limit: int = 50) -> str:
        """
        Get comments for an issue.
        
        FORMAT: get_comments(issue_id="DEMO-123", limit=50)
        
        Args:
            issue_id: The issue ID or readable ID (e.g., PROJECT-123)
            limit: Maximum number of comments to return (default: 50)
            
        Returns:
            JSON string with the list of comments
        """
        try:
            comments = self.issues_api.get_comments(issue_id, limit)
            
            # Convert to list of dictionaries
            result = []
            for comment in comments:
                if hasattr(comment, 'model_dump'):
                    comment_dict = comment.model_dump()
                else:
                    comment_dict = comment
                
                # Format the comment for better readability
                formatted_comment = {
                    "id": comment_dict.get("id"),
                    "text": comment_dict.get("text"),
                    "author": comment_dict.get("author", {}).get("name") or comment_dict.get("author", {}).get("login"),
                    "author_details": comment_dict.get("author"),
                    "created": comment_dict.get("created"),
                    "updated": comment_dict.get("updated"),
                    "deleted": comment_dict.get("deleted", False),
                    "attachments": comment_dict.get("attachments", [])
                }
                result.append(formatted_comment)
            
            return json.dumps({
                "issue_id": issue_id,
                "total_comments": len(result),
                "comments": result
            }, indent=2)
            
        except Exception as e:
            logger.exception(f"Error getting comments for issue {issue_id}")
            return json.dumps({"error": str(e)})
    
    @sync_wrapper
    def get_work_items(self, issue_id: str, limit: int = 100) -> str:
        """
        Get work items (time tracking entries) for an issue.
        
        FORMAT: get_work_items(issue_id="DEMO-123", limit=100)
        
        Args:
            issue_id: The issue ID or readable ID (e.g., PROJECT-123)
            limit: Maximum number of work items to return (default: 100)
            
        Returns:
            JSON string with the list of work items (time tracking entries)
        """
        try:
            work_items = self.issues_api.get_work_items(issue_id, limit)
            
            # Convert to list of dictionaries
            result = []
            total_minutes = 0
            
            for item in work_items:
                if hasattr(item, 'model_dump'):
                    item_dict = item.model_dump()
                else:
                    item_dict = item
                
                # Format the work item for better readability
                duration_minutes = item_dict.get("duration", 0) or 0
                total_minutes += duration_minutes
                
                formatted_item = {
                    "id": item_dict.get("id"),
                    "duration_minutes": duration_minutes,
                    "duration_hours": round(duration_minutes / 60, 2) if duration_minutes else 0,
                    "date": item_dict.get("date"),
                    "description": item_dict.get("description"),
                    "author": item_dict.get("author", {}).get("name") or item_dict.get("author", {}).get("login"),
                    "author_details": item_dict.get("author"),
                    "type": item_dict.get("type", {}).get("name") if item_dict.get("type") else None,
                    "created": item_dict.get("created"),
                    "updated": item_dict.get("updated")
                }
                result.append(formatted_item)
            
            return json.dumps({
                "issue_id": issue_id,
                "total_work_items": len(result),
                "total_duration_minutes": total_minutes,
                "total_duration_hours": round(total_minutes / 60, 2),
                "work_items": result
            }, indent=2)
            
        except Exception as e:
            logger.exception(f"Error getting work items for issue {issue_id}")
            return json.dumps({"error": str(e)})
    
    @sync_wrapper
    def get_time_tracking(self, issue_id: str) -> str:
        """
        Get time tracking summary for an issue, including estimation and spent time.
        
        FORMAT: get_time_tracking(issue_id="DEMO-123")
        
        Args:
            issue_id: The issue ID or readable ID (e.g., PROJECT-123)
            
        Returns:
            JSON string with time tracking summary including estimation, spent time, and work items
        """
        try:
            summary = self.issues_api.get_time_tracking_summary(issue_id)
            
            # Get work items for detailed breakdown
            work_items = self.issues_api.get_work_items(issue_id, limit=100)
            
            # Group work items by author
            by_author = {}
            for item in work_items:
                if hasattr(item, 'model_dump'):
                    item_dict = item.model_dump()
                else:
                    item_dict = item
                
                author_name = item_dict.get("author", {}).get("name") or item_dict.get("author", {}).get("login") or "Unknown"
                if author_name not in by_author:
                    by_author[author_name] = {
                        "total_minutes": 0,
                        "total_hours": 0,
                        "count": 0
                    }
                
                duration = item_dict.get("duration", 0) or 0
                by_author[author_name]["total_minutes"] += duration
                by_author[author_name]["count"] += 1
            
            # Calculate hours for each author
            for author_data in by_author.values():
                author_data["total_hours"] = round(author_data["total_minutes"] / 60, 2)
            
            # Enhance the summary with additional information
            enhanced_summary = {
                "issue_id": issue_id,
                "estimation": summary.get("estimation"),
                "spent_time": summary.get("spent_time"),
                "total_work_items": summary.get("work_items_count", 0),
                "total_duration": {
                    "minutes": summary.get("total_duration_minutes", 0),
                    "hours": summary.get("total_duration_hours", 0)
                },
                "breakdown_by_author": by_author
            }
            
            return json.dumps(enhanced_summary, indent=2)
            
        except Exception as e:
            logger.exception(f"Error getting time tracking for issue {issue_id}")
            return json.dumps({"error": str(e)})
    
    def close(self) -> None:
        """Close the API client."""
        self.client.close()
        
    def get_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get the definitions of all issue tools.
        
        Returns:
            Dictionary mapping tool names to their configuration
        """
        return {
            "get_issue": {
                "description": "Get information about a specific issue in YouTrack. Returns detailed information including custom fields.",
                "parameter_descriptions": {
                    "issue_id": "The issue ID or readable ID (e.g., PROJECT-123)"
                }
            },
            "search_issues": {
                "description": "Search for issues using YouTrack query language. Supports all YouTrack search syntax.",
                "parameter_descriptions": {
                    "query": "The search query (e.g., 'project: DEMO #Unresolved')",
                    "limit": "Maximum number of issues to return (optional, default: 10)"
                }
            },
            "create_issue": {
                "description": "Create a new issue in YouTrack with the specified details.",
                "parameter_descriptions": {
                    "project": "The project ID or short name (e.g., 'DEMO' or '0-0')",
                    "summary": "The issue title/summary",
                    "description": "Detailed description of the issue (optional)"
                }
            },
            "add_comment": {
                "description": "Add a comment to an existing issue in YouTrack.",
                "parameter_descriptions": {
                    "issue_id": "The issue ID or readable ID (e.g., PROJECT-123)",
                    "text": "The comment text to add to the issue"
                }
            },
            "get_comments": {
                "description": "Get all comments for a specific issue, including author information and timestamps.",
                "parameter_descriptions": {
                    "issue_id": "The issue ID or readable ID (e.g., PROJECT-123)",
                    "limit": "Maximum number of comments to return (optional, default: 50)"
                }
            },
            "get_work_items": {
                "description": "Get work items (time tracking entries) for a specific issue, showing who logged time and when.",
                "parameter_descriptions": {
                    "issue_id": "The issue ID or readable ID (e.g., PROJECT-123)",
                    "limit": "Maximum number of work items to return (optional, default: 100)"
                }
            },
            "get_time_tracking": {
                "description": "Get comprehensive time tracking summary for an issue, including estimation, spent time, and breakdown by author.",
                "parameter_descriptions": {
                    "issue_id": "The issue ID or readable ID (e.g., PROJECT-123)"
                }
            },
            "get_issue_raw": {
                "description": "Get raw information about a specific issue, bypassing the Pydantic model.",
                "parameter_descriptions": {
                    "issue_id": "The issue ID or readable ID (e.g., PROJECT-123)"
                }
            }
        }
    
    @sync_wrapper
    def get_issue_raw(self, issue_id: str) -> str:
        """
        Get raw information about a specific issue, bypassing the Pydantic model.
        
        FORMAT: get_issue_raw(issue_id="DEMO-123")
        
        Args:
            issue_id: The issue ID or readable ID
            
        Returns:
            Raw JSON string with the issue data
        """
        try:
            raw_issue = self.client.get(f"issues/{issue_id}")
            return json.dumps(raw_issue, indent=2)
        except Exception as e:
            logger.exception(f"Error getting raw issue {issue_id}")
            return json.dumps({"error": str(e)})
