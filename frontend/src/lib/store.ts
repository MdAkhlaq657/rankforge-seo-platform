import { create } from "zustand";
import Cookies from "js-cookie";
import { User, Organization } from "@/types";

interface AuthState {
  user: User | null;
  currentOrg: Organization | null;
  organizations: Organization[];
  isLoaded: boolean;
  setAuth: (user: User, org: Organization, orgs: Organization[]) => void;
  setTokens: (access: string, refresh: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  currentOrg: null,
  organizations: [],
  isLoaded: false,

  setAuth: (user, org, orgs) =>
    set({ user, currentOrg: org, organizations: orgs, isLoaded: true }),

  setTokens: (access, refresh) => {
    Cookies.set("access_token", access, { expires: 1, sameSite: "strict" });
    Cookies.set("refresh_token", refresh, { expires: 30, sameSite: "strict" });
  },

  logout: () => {
    Cookies.remove("access_token");
    Cookies.remove("refresh_token");
    set({ user: null, currentOrg: null, organizations: [], isLoaded: false });
  },
}));
