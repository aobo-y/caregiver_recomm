-- phpMyAdmin SQL Dump
-- version 4.1.14
-- http://www.phpmyadmin.net
--
-- Host: 127.0.0.1
-- Generation Time: Mar 01, 2022 at 11:13 PM
-- Server version: 5.6.17
-- PHP Version: 5.5.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;

--
-- Database: `ema`
--

-- --------------------------------------------------------

--
-- Table structure for table `ema_storing_data`
--

CREATE TABLE IF NOT EXISTS `ema_storing_data` (
  `speakerID` int(255) DEFAULT NULL,
  `time` datetime(6) NOT NULL,
  `event_vct` varchar(5000) DEFAULT NULL,
  `stats_vct` varchar(5000) DEFAULT NULL,
  `action` int(10) DEFAULT NULL,
  `reward` float DEFAULT NULL,
  `action_vct` varchar(5000) DEFAULT NULL,
  `message_name` varchar(5000) DEFAULT NULL,
  `reactive` int(100) DEFAULT NULL,
  `trigger_origin` varchar(5000) DEFAULT NULL,
  `baseline_period` int(255) DEFAULT NULL,
  `reactive_check_in` int(255) DEFAULT NULL,
  `deployment_id` varchar(5000) DEFAULT NULL,
  `uploaded` int(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`time`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
