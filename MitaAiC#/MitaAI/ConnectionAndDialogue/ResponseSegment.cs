using MelonLoader;
using System;
using System.Collections.Generic;
using System.Text.Json;

namespace MitaAI
{
    public class ResponseSegment
    {
        public string text { get; set; } = "";
        public List<string> emotions { get; set; } = new List<string>();
        public List<string> animations { get; set; } = new List<string>();
        public List<string> commands { get; set; } = new List<string>();
        public List<string> movement_modes { get; set; } = new List<string>();
        public List<string> visual_effects { get; set; } = new List<string>();
        public List<string> clothes { get; set; } = new List<string>();
        public List<string> music { get; set; } = new List<string>();
        public List<string> interactions { get; set; } = new List<string>();
        public List<string> face_params { get; set; } = new List<string>();
        public string hint { get; set; } = null;
        public string target { get; set; } = null;
        public bool? allow_sleep { get; set; } = null;

        public static List<ResponseSegment> ParseList(JsonElement json)
        {
            var segments = new List<ResponseSegment>();
            try
            {
                foreach (var segJson in json.EnumerateArray())
                {
                    var seg = new ResponseSegment();
                    if (segJson.TryGetProperty("text", out var text))
                        seg.text = text.GetString() ?? "";
                    seg.emotions = ParseStringList(segJson, "emotions");
                    seg.animations = ParseStringList(segJson, "animations");
                    seg.commands = ParseStringList(segJson, "commands");
                    seg.movement_modes = ParseStringList(segJson, "movement_modes");
                    seg.visual_effects = ParseStringList(segJson, "visual_effects");
                    seg.clothes = ParseStringList(segJson, "clothes");
                    seg.music = ParseStringList(segJson, "music");
                    seg.interactions = ParseStringList(segJson, "interactions");
                    seg.face_params = ParseStringList(segJson, "face_params");
                    if (segJson.TryGetProperty("hint", out var hint) && hint.ValueKind != JsonValueKind.Null)
                        seg.hint = hint.GetString();
                    if (segJson.TryGetProperty("target", out var target) && target.ValueKind != JsonValueKind.Null)
                        seg.target = target.GetString();
                    if (segJson.TryGetProperty("allow_sleep", out var allowSleep))
                    {
                        if (allowSleep.ValueKind == JsonValueKind.True) seg.allow_sleep = true;
                        else if (allowSleep.ValueKind == JsonValueKind.False) seg.allow_sleep = false;
                    }
                    segments.Add(seg);
                }
            }
            catch (Exception ex)
            {
                MelonLogger.Error($"ResponseSegment.ParseList error: {ex}");
            }
            return segments;
        }

        private static List<string> ParseStringList(JsonElement json, string key)
        {
            var list = new List<string>();
            if (json.TryGetProperty(key, out var prop) && prop.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in prop.EnumerateArray())
                {
                    var s = item.GetString();
                    if (s != null) list.Add(s);
                }
            }
            return list;
        }
    }
}
