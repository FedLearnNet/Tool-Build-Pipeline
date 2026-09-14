from typing import Optional

from pydantic import BaseModel, Field


class StatusUpdateDTO(BaseModel):
    """
    Pydantic DTO for sending status updates to the server.
    Ensures data consistency and provides validation.
    Field names use snake_case for Python and are aliased to camelCase for JSON.
    """
    step_name: str = Field(alias='stepName')
    status: str
    logs: Optional[str] = None
    progress: Optional[int] = None
    error_code: Optional[str] = Field(alias='errorCode', default=None)
    error_message: Optional[str] = Field(alias='errorMessage', default=None)

    class Config:
        populate_by_name = True


class PipelineRunInfoDTO(BaseModel):
    """ DTO for receiving build info from the server. """
    git_repo_url: str = Field(alias='gitRepoUrl')
    image_name: str = Field(alias='imageName')
    docker_tag: str = Field(alias='dockerTag')

    class Config:
        populate_by_name = True


class FileDTO(BaseModel):
    """ DTO for a file to be injected into the build context. """
    file_path: str = Field(alias='filePath')
    content: str  # Base64 encoded content

    class Config:
        populate_by_name = True
