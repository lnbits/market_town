# Description: Add your page endpoints here.


from fastapi import APIRouter, Depends
from lnbits.core.views.generic import index, index_public
from lnbits.decorators import check_account_exists
from lnbits.helpers import template_renderer

market_town_generic_router = APIRouter()


def market_town_renderer():
    return template_renderer(["market_town/templates"])


#######################################
##### ADD YOUR PAGE ENDPOINTS HERE ####
#######################################


# Backend admin page
market_town_generic_router.add_api_route(
    "/", methods=["GET"], endpoint=index, dependencies=[Depends(check_account_exists)]
)


# Frontend shareable page


market_town_generic_router.add_api_route("/{world_id}", methods=["GET"], endpoint=index_public)


