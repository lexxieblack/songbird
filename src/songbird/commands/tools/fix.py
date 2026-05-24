"""Link fixer command handler."""

from songbird.services.link_fixer import LinkFixerService
from songbird.utils.logging import get_logger


class FixHandler:
    def __init__(self, link_fixer_service: LinkFixerService) -> None:
        self.link_fixer_service = link_fixer_service
        self.logger = get_logger(__name__)

    async def fix_link(self, link: str) -> str:
        fixed_link = await self.link_fixer_service.fix(link)
        self.logger.debug("Fixed link", link=link, fixed_link=fixed_link)

        return fixed_link
