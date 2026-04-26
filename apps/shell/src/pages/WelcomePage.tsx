/**
 * WelcomePage — animated entry point at "/".
 *
 * Three CSS-driven beats:
 * 1. Logo orb fades in and starts pulsing.
 * 2. Tagline ("Frusta Oracle Builder") fades in 600ms later.
 * 3. CTA + "skippa" link appear last.
 *
 * Once the user clicks "Inizia" we set ``localStorage.fob_seen_welcome``;
 * the App router uses that flag to redirect future visits to /home so
 * the welcome doesn't get in the way after the first run. A small
 * "Salta" link offers an immediate escape.
 */

import { Box, Button, Group, Stack, Text, Title } from "@mantine/core";
import { IconArrowRight, IconSparkles } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import { markWelcomeSeen } from "../state/welcome";

export function WelcomePage() {
  const navigate = useNavigate();

  const enter = () => {
    markWelcomeSeen();
    navigate("/home");
  };

  return (
    <Box
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Decorative twinkling stars - just a few absolutely-positioned dots. */}
      {Array.from({ length: 24 }).map((_, i) => (
        <Box
          key={i}
          className="fob-twinkle"
          style={{
            position: "absolute",
            width: i % 5 === 0 ? 3 : 2,
            height: i % 5 === 0 ? 3 : 2,
            borderRadius: "50%",
            backgroundColor: "rgba(195, 174, 255, 0.8)",
            top: `${(i * 37) % 100}%`,
            left: `${(i * 53) % 100}%`,
            animationDelay: `${(i * 0.13) % 2}s`,
          }}
        />
      ))}

      <Stack align="center" gap="xl" style={{ zIndex: 1 }}>
        {/* Glowing logo orb */}
        <Box
          className="fob-pulse-glow fob-fade-in"
          style={{
            width: 140,
            height: 140,
            borderRadius: "50%",
            background:
              "radial-gradient(circle at 30% 30%, #c5aaff 0%, #6e26ff 50%, #2c0d70 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "2px solid rgba(195, 174, 255, 0.4)",
          }}
        >
          <IconSparkles size={56} color="#fff8e1" />
        </Box>

        {/* Tagline */}
        <Stack
          align="center"
          gap={6}
          className="fob-fade-in"
          style={{ animationDelay: "0.6s" }}
        >
          <Title
            order={1}
            style={{
              fontSize: "3.2rem",
              letterSpacing: "0.05em",
              textShadow: "0 0 24px rgba(167, 139, 255, 0.5)",
              textAlign: "center",
            }}
          >
            FOB
          </Title>
          <Text
            size="lg"
            c="dimmed"
            style={{ letterSpacing: "0.15em", textTransform: "uppercase" }}
          >
            Frusta Oracle Builder
          </Text>
          <Text size="sm" c="dimmed" style={{ marginTop: 8, textAlign: "center" }}>
            L'oracolo del tuo prossimo personaggio in Path of Exile
          </Text>
        </Stack>

        {/* CTAs */}
        <Group
          gap="md"
          className="fob-fade-in"
          style={{ animationDelay: "1.2s" }}
        >
          <Button
            size="lg"
            rightSection={<IconArrowRight size={20} />}
            onClick={enter}
            style={{
              boxShadow: "0 0 20px rgba(110, 38, 255, 0.6)",
            }}
          >
            Inizia
          </Button>
        </Group>
      </Stack>
    </Box>
  );
}
