-- phpMyAdmin SQL Dump
-- version 4.1.14
-- http://www.phpmyadmin.net
--
-- Host: 127.0.0.1
-- Generation Time: Jun 26, 2020 at 03:56 AM
-- Server version: 5.6.17-log
-- PHP Version: 5.5.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";

-- CREATE DATABASE alzheimer_test_data;
USE alzheimer_test_data;

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `ema`
--

-- --------------------------------------------------------

--
-- Table structure for table `ema_data`
--

CREATE TABLE IF NOT EXISTS `ema_data` (
  `suid` int(11) NOT NULL DEFAULT '1',
  `primkey` varchar(150) NOT NULL,
  `variablename` varchar(150) NOT NULL,
  `answer` varchar(150), -- previously blob, changed into string to provide simplicity
  `dirty` int(11) NOT NULL DEFAULT '0',
  `language` int(11) NOT NULL,
  `mode` int(11) NOT NULL,
  `version` int(11) NOT NULL,
  `completed` int(11) NOT NULL DEFAULT '0',
  `synced` int(11) NOT NULL DEFAULT '0',
  `ts` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`suid`,`primkey`,`variablename`),
  KEY `variablenameindex` (`suid`,`variablename`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
