/**
 * AegisAI Disaster Service Façade
 * Backward-compatible bridge delegating to modular domain services:
 * incidentService, missionService, hospitalService, resourceService, and authService.
 */

import { incidentService } from "./incidentService";
import { missionService } from "./missionService";
import { hospitalService } from "./hospitalService";
import { resourceService } from "./resourceService";

// ============================================================
// INCIDENTS / DISASTERS
// ============================================================
export const getDisasters = (params) => incidentService.getIncidents(params);
export const getDisaster = (id) => incidentService.getIncident(id);
export const createDisaster = (data) => incidentService.createIncident(data);
export const updateDisaster = (id, data) => incidentService.updateIncident(id, data);

// ============================================================
// GEOSPATIAL & SMART DISPATCH RECOMMENDATIONS
// ============================================================
export const getNearestRescueTeam = (disasterId) => incidentService.getNearestRescueTeam(disasterId);
export const getRecommendedRescueTeams = (disasterId, limit = 5) => incidentService.getRecommendedRescueTeams(disasterId, limit);
export const getRouteToRescueTeam = (disasterId, teamId) => incidentService.getRouteToRescueTeam(disasterId, teamId);

// ============================================================
// MISSIONS & ASSIGNMENTS
// ============================================================
export const getMissions = (activeOnly) => missionService.getMissions(activeOnly);
export const createAssignment = (disasterId, teamId, _token, options = {}) => missionService.createAssignment(disasterId, teamId, options);
export const getAssignments = (_token, params = {}) => missionService.getAssignments(params);
export const updateAssignmentStatus = (assignmentId, status, _token) => missionService.updateAssignmentStatus(assignmentId, status);
export const completeAssignment = (assignmentId, _token) => missionService.updateAssignmentStatus(assignmentId, "COMPLETED");

// ============================================================
// HOSPITALS
// ============================================================
export const getHospitals = (operationalOnly) => hospitalService.getHospitals(operationalOnly);
export const getHospital = (id) => hospitalService.getHospital(id);

// ============================================================
// SHELTERS & RESCUE TEAMS
// ============================================================
export const getShelters = () => resourceService.getShelters();
export const getRescueTeams = (statusFilter) => resourceService.getRescueTeams(statusFilter);

export default {
    getDisasters,
    getDisaster,
    createDisaster,
    updateDisaster,
    getNearestRescueTeam,
    getRecommendedRescueTeams,
    getRouteToRescueTeam,
    getMissions,
    createAssignment,
    getAssignments,
    updateAssignmentStatus,
    completeAssignment,
    getHospitals,
    getHospital,
    getShelters,
    getRescueTeams
};