import AccountCircleIcon from "@mui/icons-material/AccountCircle";
import LinkIcon from "@mui/icons-material/Link";
import LockIcon from "@mui/icons-material/Lock";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import SaveIcon from "@mui/icons-material/Save";
import SecurityIcon from "@mui/icons-material/Security";
import TuneIcon from "@mui/icons-material/Tune";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  Grid,
  Slider,
  Snackbar,
  Switch,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import apiService from "../services/apiService";
import { formatAddress } from "../utils/formatters";

const Settings = () => {
  const { user, logout } = useAuth();

  const [account, setAccount] = useState({
    email: user?.email || "",
    username: user?.username || "",
  });

  const [prefs, setPrefs] = useState({
    notifications: true,
    darkMode: true,
    autoRebalance: false,
    emailAlerts: true,
    riskAlerts: true,
  });

  const [riskTolerance, setRiskTolerance] = useState(50);

  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success",
  });

  const [onchainCheck, setOnchainCheck] = useState({
    status: "idle", // idle | loading | found | not_found | error
    data: null,
    message: "",
  });

  // Correct handler for text fields
  const handleAccountChange = (field) => (e) => {
    setAccount((prev) => ({ ...prev, [field]: e.target.value }));
  };

  // Correct handler for Switch — uses e.target.checked, not e.target.value
  const handlePrefSwitch = (field) => (e) => {
    setPrefs((prev) => ({ ...prev, [field]: e.target.checked }));
  };

  const handleSave = () => {
    setSnackbar({
      open: true,
      message: "Settings saved successfully!",
      severity: "success",
    });
  };

  const handleLogout = () => {
    logout();
  };

  const walletAddress = user?.wallet_address || user?.address || "";

  const handleVerifyOnchain = async () => {
    if (!walletAddress) return;
    setOnchainCheck({ status: "loading", data: null, message: "" });
    try {
      const res = await apiService.portfolio.getOnchain(walletAddress);
      setOnchainCheck({
        status: "found",
        data: res.data || res,
        message: "",
      });
    } catch (err) {
      const status = err?.response?.status;
      if (status === 404) {
        setOnchainCheck({
          status: "not_found",
          data: null,
          message:
            "No portfolio has been recorded on-chain for this wallet yet.",
        });
      } else {
        setOnchainCheck({
          status: "error",
          data: null,
          message: err.message || "Could not reach the blockchain node.",
        });
      }
    }
  };

  return (
    <Box className="fade-in">
      <Typography variant="h4" component="h1" gutterBottom>
        Settings
      </Typography>

      <Grid container spacing={3}>
        {/* Account Settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              title="Account"
              avatar={<AccountCircleIcon color="primary" />}
            />
            <Divider />
            <CardContent>
              <TextField
                fullWidth
                label="Username"
                value={account.username}
                onChange={handleAccountChange("username")}
                margin="normal"
              />
              <TextField
                fullWidth
                label="Email"
                type="email"
                value={account.email}
                onChange={handleAccountChange("email")}
                margin="normal"
              />
              <TextField
                fullWidth
                label="Wallet Address"
                value={walletAddress}
                margin="normal"
                disabled
                helperText={
                  walletAddress ? `Full: ${walletAddress}` : "Not connected"
                }
              />

              {walletAddress && (
                <Box sx={{ mt: 2 }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1.5,
                      flexWrap: "wrap",
                    }}
                  >
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={
                        onchainCheck.status === "loading" ? (
                          <CircularProgress size={16} />
                        ) : (
                          <LinkIcon />
                        )
                      }
                      onClick={handleVerifyOnchain}
                      disabled={onchainCheck.status === "loading"}
                    >
                      Verify On-Chain Portfolio
                    </Button>
                    {onchainCheck.status === "found" && (
                      <Chip
                        size="small"
                        color="success"
                        label={`Found on-chain (v${onchainCheck.data?.version ?? "?"})`}
                      />
                    )}
                    {onchainCheck.status === "not_found" && (
                      <Chip
                        size="small"
                        color="warning"
                        label="Not found on-chain"
                      />
                    )}
                    {onchainCheck.status === "error" && (
                      <Chip
                        size="small"
                        color="error"
                        label="Blockchain unreachable"
                      />
                    )}
                  </Box>
                  {onchainCheck.status === "found" && onchainCheck.data && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mt: 1 }}
                    >
                      Assets: {onchainCheck.data.assets?.join(", ") || "—"} on{" "}
                      {onchainCheck.data.network || "chain"}
                    </Typography>
                  )}
                  {(onchainCheck.status === "not_found" ||
                    onchainCheck.status === "error") && (
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{ mt: 1 }}
                    >
                      {onchainCheck.message}
                    </Typography>
                  )}
                </Box>
              )}

              <Box sx={{ mt: 3, display: "flex", gap: 2, flexWrap: "wrap" }}>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={handleSave}
                >
                  Save Changes
                </Button>
                <Button variant="outlined" color="error" onClick={handleLogout}>
                  Logout
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Preferences */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              title="Preferences"
              avatar={<NotificationsActiveIcon color="primary" />}
            />
            <Divider />
            <CardContent>
              <FormControlLabel
                control={
                  <Switch
                    checked={prefs.notifications}
                    onChange={handlePrefSwitch("notifications")}
                  />
                }
                label="Enable Push Notifications"
                sx={{ display: "flex", mb: 1 }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={prefs.emailAlerts}
                    onChange={handlePrefSwitch("emailAlerts")}
                  />
                }
                label="Email Alerts"
                sx={{ display: "flex", mb: 1 }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={prefs.riskAlerts}
                    onChange={handlePrefSwitch("riskAlerts")}
                  />
                }
                label="Risk Threshold Alerts"
                sx={{ display: "flex", mb: 1 }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={prefs.autoRebalance}
                    onChange={handlePrefSwitch("autoRebalance")}
                  />
                }
                label="Auto-Rebalance Portfolio"
                sx={{ display: "flex", mb: 1 }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={prefs.darkMode}
                    onChange={handlePrefSwitch("darkMode")}
                  />
                }
                label="Dark Mode"
                sx={{ display: "flex", mb: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Risk Profile */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              title="Risk Profile"
              avatar={<TuneIcon color="primary" />}
            />
            <Divider />
            <CardContent>
              <Box sx={{ mb: 2 }}>
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    mb: 1,
                  }}
                >
                  <Typography variant="subtitle2">
                    Default Risk Tolerance
                  </Typography>
                  <Typography
                    variant="body2"
                    color={
                      riskTolerance < 33
                        ? "success.main"
                        : riskTolerance < 67
                          ? "warning.main"
                          : "error.main"
                    }
                    sx={{ fontWeight: 600 }}
                  >
                    {riskTolerance < 33
                      ? "Conservative"
                      : riskTolerance < 67
                        ? "Moderate"
                        : "Aggressive"}{" "}
                    ({riskTolerance})
                  </Typography>
                </Box>
                <Slider
                  value={riskTolerance}
                  onChange={(_, v) => setRiskTolerance(v)}
                  min={0}
                  max={100}
                  step={5}
                  marks={[
                    { value: 0, label: "0" },
                    { value: 50, label: "50" },
                    { value: 100, label: "100" },
                  ]}
                  valueLabelDisplay="auto"
                  color={
                    riskTolerance < 33
                      ? "success"
                      : riskTolerance < 67
                        ? "warning"
                        : "error"
                  }
                />
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    mt: 0.5,
                  }}
                >
                  <Typography variant="caption" color="text.secondary">
                    Conservative
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Aggressive
                  </Typography>
                </Box>
              </Box>
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleSave}
              >
                Save Profile
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Security */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader
              title="Security"
              avatar={<SecurityIcon color="primary" />}
            />
            <Divider />
            <CardContent>
              <Alert severity="info" sx={{ mb: 2 }}>
                Your session is secured via wallet-based authentication.
              </Alert>
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Connected Wallet
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: "monospace",
                    backgroundColor: "rgba(255,255,255,0.04)",
                    p: 1,
                    borderRadius: 1,
                    wordBreak: "break-all",
                  }}
                >
                  {walletAddress || "Not connected"}
                </Typography>
              </Box>
              <Box sx={{ mb: 2 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  Display (Shortened)
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {walletAddress ? formatAddress(walletAddress) : "—"}
                </Typography>
              </Box>
              <Button
                variant="outlined"
                color="error"
                startIcon={<LockIcon />}
                onClick={handleLogout}
                fullWidth
              >
                Sign Out
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
          severity={snackbar.severity}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Settings;
