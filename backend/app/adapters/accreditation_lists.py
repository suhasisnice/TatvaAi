from app.adapters.base import Result, call


def naac_grades() -> Result:
    return call("NAAC grades (MOCK)", "/naac/grades")


def nba_accredited() -> Result:
    return call("NBA accredited list (MOCK)", "/nba/accredited")


def nirf_list() -> Result:
    return call("NIRF list (MOCK)", "/nirf/list")
